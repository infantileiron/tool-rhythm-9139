import csv
import io
import logging

from fastapi import HTTPException
from redis.exceptions import RedisError

from src.config.database import database
from src.config.queue import QUEUE_KEY, redis
from src.constants.domain import ALGORITHM, BANDS, EXCEPTIONS, ReconState, Role, RunStatus
from src.models.ledger import audit, records_by_ids, records_in_window, stations
from src.models.runs import list_runs, run_record
from src.services.reconcile import reconcile
from src.utils.serialize import canonical, fingerprint


def reconciliation(cursor, start, end):
    sites = stations(cursor)
    records = records_in_window(cursor, start, end)
    return sites, reconcile(records, sites)


def snapshot(cursor, params):
    sites = stations(cursor)
    if len(sites) > 250:
        raise HTTPException(422, '当前站点超过单次计算上限 250 个')
    sites, ledger = reconciliation(cursor, params.start, params.end)
    return {'algorithm': ALGORITHM, 'bands': BANDS,
            'params': params.model_dump(mode='json', exclude={'title'}),
            'stations': [{'code': site['code'], 'name': site['name'],
                          'counts': ledger['stations'][site['code']]['counts'],
                          'actual': ledger['stations'][site['code']]['actual'],
                          'disputed': ledger['stations'][site['code']]['disputed'],
                          'credential': ledger['stations'][site['code']]['credential'],
                          'recon_state': ledger['stations'][site['code']]['state'],
                          'recon_refs': [record['id'] for record in ledger['stations'][site['code']]['records']
                                         if record['id'] is not None],
                          'unresolved_refs': [record['id'] for record in ledger['stations'][site['code']]['unresolved']
                                              if record['id'] is not None]}
                         for site in sites],
            'unattributed_refs': [record['id'] for record in ledger['unattributed']
                                  if record['id'] is not None]}


def queue_run(params, actor):
    with database() as cursor:
        inputs = snapshot(cursor, params)
        checksum = fingerprint(inputs)
        cursor.execute('INSERT INTO runs(title,creator,snapshot,checksum) VALUES(%s,%s,%s,%s)',
                       (params.title, actor, canonical(inputs), checksum))
        run_id = cursor.lastrowid
        audit(cursor, actor, 'run.queue', str(run_id), {'checksum': checksum})
    try:
        with redis.pipeline() as signals:
            signals.lpush(QUEUE_KEY, run_id).ltrim(QUEUE_KEY, 0, 99).execute()
    except RedisError:
        logging.warning('Redis wake failed for run %s; database polling remains active', run_id)
    return {'id': run_id, 'checksum': checksum, 'status': RunStatus.QUEUED}


def summaries(viewer):
    with database() as cursor:
        return list_runs(cursor, viewer['role'] == Role.OBSERVER)


def details(run_id, viewer):
    with database() as cursor:
        run = run_record(cursor, run_id)
    if not run or (viewer['role'] == Role.OBSERVER and run['status'] != RunStatus.PUBLISHED):
        raise HTTPException(404, '找不到可查看的方案版本')
    return run


def trace(run_id, viewer):
    """分型页面逐站追溯：该版本用了哪些记录、哪些还没对上。

    记录按版本快照里的引用取回，因此后来补录或校正不会改变旧版本用的记录；
    对账状态、槽位与争议仍由同一批记录复算得出。
    """
    run = details(run_id, viewer)
    params = run['snapshot']['params']
    snapshot_sites = {site['code']: site for site in run['snapshot']['stations']}
    refs = set()
    for site in run['snapshot']['stations']:
        refs.update(site.get('recon_refs') or [])
        refs.update(site.get('unresolved_refs') or [])
    refs.update(run['snapshot'].get('unattributed_refs') or [])
    with database() as cursor:
        sites = stations(cursor)
        records = records_by_ids(cursor, sorted(refs)) if refs else []
        ledger = reconcile(records, sites)
    stations_report = {}
    for site in sites:
        report = ledger['stations'][site['code']]
        frozen = snapshot_sites.get(site['code'], {})
        used = set(frozen.get('recon_refs') or [])
        pending = set(frozen.get('unresolved_refs') or [])
        stations_report[site['code']] = {
            'code': site['code'], 'name': site['name'], 'state': frozen.get('recon_state', report['state']),
            'actual': frozen.get('actual', report['actual']),
            'disputed': frozen.get('disputed', report['disputed']),
            'credential': frozen.get('credential', report['credential']),
            'counts': frozen.get('counts', report['counts']),
            'slots': [{**slot, 'used_refs': _slot_refs(report, slot, used),
                       'pending_refs': _slot_refs(report, slot, pending)}
                      for slot in report['slots']],
            'records': [{**record, 'used': record['id'] in used, 'pending': record['id'] in pending}
                        for record in report['records']
                        if record['id'] in used or record['id'] in pending],
            'unresolved': [{**record, 'pending': True} for record in report['unresolved']],
        }
    unattributed = [{**record, 'used': record['id'] in refs} for record in ledger['unattributed']
                    if record['id'] in refs]
    return {'run': {'id': run['id'], 'title': run['title'], 'status': run['status'],
                    'checksum': run['checksum'], 'params': params},
            'stations': stations_report, 'unattributed': unattributed,
            'stats': ledger['stats']}


def _slot_refs(report, slot, selections):
    return [record['id'] for record in report['records']
            if record['id'] in selections and record['day'] == slot['day']
            and record['hour'] == slot['hour']]



def publish(run_id, data, actor):
    with database() as cursor:
        run = run_record(cursor, run_id, lock=True)
        if not run:
            raise HTTPException(404, '找不到方案版本')
        if run['status'] != RunStatus.READY:
            raise HTTPException(409, '仅待复核的版本可以发布')
        expected_groups = {group['key'] for group in run['result']['groups']}
        expected_exceptions = {m['code'] for m in run['result']['members'] if m['status'] in EXCEPTIONS}
        if expected_groups != data.groups.keys() or expected_exceptions != data.exceptions.keys():
            raise HTTPException(422, '请填写全部分组的值守安排及全部例外站点的处理意见')
        decision = {**data.model_dump(), 'reviewer': actor}
        cursor.execute("UPDATE runs SET status='published',decision=%s,published_at=UTC_TIMESTAMP() WHERE id=%s",
                       (canonical(decision), run_id))
        audit(cursor, actor, 'run.publish', str(run_id), {'checksum': run['checksum'], **decision})
    return details(run_id, {'role': Role.ADMIN})


def spreadsheet_text(value):
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def export_csv(run):
    if run['status'] != RunStatus.PUBLISHED:
        raise HTTPException(409, '发布后可以导出值班单')
    params = run['snapshot']['params']
    decision = run['decision']
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['版本', '输入校验值', '起日', '止日', '站点编号', '站点名称', '类型', '分组',
                     '实收件数', '争议件数', '凭证件数', '对账状态',
                     *[f'{a:02d}:00–{b:02d}:00' for a, b in run['snapshot']['bands']],
                     '值守或复核处置', '发布人', '复核说明'])
    labels = {ReconState.CLEAN: '已对账', ReconState.PARTIAL: '部分对上',
              ReconState.UNRECONCILED: '未对账', ReconState.NO_DATA: '无记录'}
    for member in run['result']['members']:
        action = (decision['groups'][member['group']] if member['group'] else
                  decision['exceptions'][member['code']])
        writer.writerow([run['id'], run['checksum'], params['start'], params['end'], member['code'],
                         spreadsheet_text(member['name']), member['status'], member['group'],
                         member.get('actual', member['total']), member.get('disputed', 0),
                         member.get('credential', member['total']),
                         labels.get(member.get('recon_state'), '—'), *member['counts'],
                         spreadsheet_text(action),
                         decision['reviewer'], spreadsheet_text(decision['memo'])])
    return '\ufeff' + out.getvalue()
