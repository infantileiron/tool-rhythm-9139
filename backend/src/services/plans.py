import csv
import io
import logging

from fastapi import HTTPException
from redis.exceptions import RedisError

from src.config.database import database
from src.config.queue import QUEUE_KEY, redis
from src.constants.domain import ALGORITHM, BANDS, EXCEPTIONS, Role, RunStatus
from src.models.ledger import audit, stations
from src.models.runs import list_runs, run_record
from src.utils.serialize import canonical, fingerprint


def snapshot(cursor, params):
    sites = stations(cursor)
    if len(sites) > 250:
        raise HTTPException(422, '当前站点超过单次计算上限 250 个')
    totals = {site['code']: [0] * len(BANDS) for site in sites}
    cursor.execute('SELECT station_code,hour,SUM(quantity) AS quantity FROM return_records '
                   'WHERE day BETWEEN %s AND %s GROUP BY station_code,hour', (params.start, params.end))
    hour_bands = {hour: index for index, (a, b) in enumerate(BANDS) for hour in range(a, b)}
    for row in cursor.fetchall():
        totals[row['station_code']][hour_bands[row['hour']]] += int(row['quantity'])
    return {'algorithm': ALGORITHM, 'bands': BANDS,
            'params': params.model_dump(mode='json', exclude={'title'}),
            'stations': [{'code': site['code'], 'name': site['name'], 'counts': totals[site['code']]}
                         for site in sites]}


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
                     '归还件数', *[f'{a:02d}:00–{b:02d}:00' for a, b in run['snapshot']['bands']],
                     '值守或复核处置', '发布人', '复核说明'])
    for member in run['result']['members']:
        action = (decision['groups'][member['group']] if member['group'] else
                  decision['exceptions'][member['code']])
        writer.writerow([run['id'], run['checksum'], params['start'], params['end'], member['code'],
                         spreadsheet_text(member['name']), member['status'], member['group'],
                         member['total'], *member['counts'], spreadsheet_text(action),
                         decision['reviewer'], spreadsheet_text(decision['memo'])])
    return '\ufeff' + out.getvalue()
