from fastapi import HTTPException
from pymysql.err import IntegrityError

from src.config.database import database
from src.constants.domain import MAX_IMPORT_ROWS, Channel
from src.models.ledger import audit, list_records, records_in_window, stations
from src.services.reconcile import parse_csv, reconcile
from src.utils.serialize import fingerprint


def station_list():
    with database() as cursor:
        return stations(cursor)


def create_station(data, actor):
    try:
        with database() as cursor:
            cursor.execute('INSERT INTO stations(code,name,address,steward) VALUES(%s,%s,%s,%s)',
                           (data.code, data.name, data.address, data.steward))
            audit(cursor, actor, 'station.create', data.code, data.model_dump())
    except IntegrityError as error:
        if error.args[0] == 1062:
            raise HTTPException(409, '站点编号已登记') from error
        raise
    return data


def records(period, station_code, channel, page):
    with database() as cursor:
        return list_records(cursor, period, station_code, channel, page)


STATE_LABELS = {'clean': '已对账', 'partial': '部分对上', 'unreconciled': '未对账', 'no_data': '无记录'}
STATE_NOTES = {
    'clean': '两路记录逐槽对上，可直接参与分型。',
    'partial': '已有可计入的实收，但仍有未落位或争议记录；实收达到件数门槛时可照常分型，留下追溯。',
    'unreconciled': '实收为零，或未落位、争议件数过多，无法可靠代表该站节律；不参与分型，列为例外核实。',
    'no_data': '窗口内没有任何归还记录，需联系站点确认开放与漏录情况。',
}


def reconciliation_view(period, station_code):
    """台账对账视图：逐站实收、争议、未对上记录，以及选中站的槽位明细。"""
    with database() as cursor:
        sites = stations(cursor)
        records = records_in_window(cursor, period.start, period.end)
        ledger = reconcile(records, sites)
    summaries = []
    for site in sites:
        report = ledger['stations'][site['code']]
        summaries.append({
            'code': site['code'], 'name': site['name'], 'state': report['state'],
            'state_label': STATE_LABELS[report['state']], 'note': STATE_NOTES[report['state']],
            'actual': report['actual'], 'disputed': report['disputed'],
            'credential': report['credential'], 'counts': report['counts'],
            'slot_count': len(report['slots']), 'unresolved_count': len(report['unresolved']),
            'record_count': len(report['records']),
        })
    detail = None
    if station_code:
        report = ledger['stations'].get(station_code)
        detail = report or None
    return {'stats': ledger['stats'], 'stations': summaries, 'detail': detail,
            'unattributed': ledger['unattributed']}


def batch_checksum(channel, content, default_station, default_day, start, end):
    """同一批联单的指纹：内容、默认补齐值和窗口相同即视为同一批。"""
    return fingerprint({'channel': channel, 'content': content,
                        'default_station': default_station or '',
                        'default_day': str(default_day or ''), 'start': str(start), 'end': str(end)})


def import_batch(data, actor):
    """导入一路归还联。同一内容重复导入不新增记录，也不重复计件。"""
    if data.channel not in (Channel.CABINET, Channel.PAPER):
        raise HTTPException(422, '来源通道只能是 cabinet 或 paper')
    if len(data.content) > 4 * 1024 * 1024:
        raise HTTPException(422, '联单文件超过 4 MB 上限')
    checksum = batch_checksum(data.channel, data.content, data.default_station,
                              data.default_day, data.start, data.end)
    rows, issues = parse_csv(data.content, data.channel,
                             default_station=data.default_station, default_day=data.default_day,
                             period_start=data.start, period_end=data.end)
    if issues:
        raise HTTPException(422, {'message': '联单存在无法读取的行，整批未导入', 'rows': issues[:20]})
    if not rows:
        raise HTTPException(422, '联单没有可导入的数据行')
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(422, f'单批最多导入 {MAX_IMPORT_ROWS} 行')
    with database() as cursor:
        cursor.execute('SELECT * FROM import_batches WHERE checksum=%s', (checksum,))
        existing = cursor.fetchone()
        if existing:
            return {'batch': existing, 'replayed': True, 'issues': []}
        station_codes = {row['station_code'] for row in rows if row['station_code']}
        if station_codes:
            placeholders = ','.join(['%s'] * len(station_codes))
            cursor.execute(f'SELECT code FROM stations WHERE code IN ({placeholders})',
                           sorted(station_codes))
            found = {row['code'] for row in cursor.fetchall()}
            unknown = sorted(station_codes - found)
            if unknown:
                raise HTTPException(422, f'站点尚未登记：{"、".join(unknown)}')
        placed = [row for row in rows if row['station_code'] and row['day']]
        existing_slots = {}
        if placed:
            days = sorted({row['day'] for row in placed})
            codes = sorted({row['station_code'] for row in placed})
            cursor.execute('SELECT station_code,day,hour,quantity,batch_id,row_no FROM return_records '
                           'WHERE channel=%s AND day BETWEEN %s AND %s AND station_code IN '
                           f'({",".join(["%s"] * len(codes))})',
                           [data.channel, days[0], days[-1], *codes])
            for found_row in cursor.fetchall():
                existing_slots[(found_row['station_code'], str(found_row['day']), found_row['hour'])] = (
                    int(found_row['quantity']), found_row['batch_id'], found_row['row_no'])
        conflicts = [f"{row['station_code']} {row['day']} {row['hour']}:00 已有 {existing_slots[key][0]} 件，"
                     f"本批为 {row['quantity']} 件"
                     for row in placed
                     for key in [(row['station_code'], row['day'], row['hour'])]
                     if key in existing_slots and existing_slots[key][0] != row['quantity']]
        if conflicts:
            raise HTTPException(422, {'message': '同通道下已有不同件数的记录，整批未导入；请改用人工校正在台账中合并',
                                      'rows': conflicts[:20]})
        cursor.execute('INSERT INTO import_batches(channel,filename,checksum,period_start,period_end,actor,'
                       'rows_total,rows_inserted,rows_duplicate,rows_unresolved) '
                       'VALUES(%s,%s,%s,%s,%s,%s,%s,0,0,0)',
                       (data.channel, data.filename, checksum, data.start, data.end, actor, len(rows)))
        batch_id = cursor.lastrowid
        inserted = duplicate = unresolved = 0
        for row in rows:
            key = (row['station_code'], row['day'], row['hour'])
            if key in existing_slots:
                duplicate += 1
                continue
            unresolved += not row['station_code'] or not row['day']
            cursor.execute('INSERT INTO return_records(channel,station_code,day,hour,quantity,source,'
                           'batch_id,row_no) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                           (data.channel, row['station_code'], row['day'], row['hour'],
                            row['quantity'], row['source'] or data.filename, batch_id, row['row_no']))
            inserted += 1
        cursor.execute('UPDATE import_batches SET rows_inserted=%s,rows_duplicate=%s,rows_unresolved=%s '
                       'WHERE id=%s', (inserted, duplicate, unresolved, batch_id))
        audit(cursor, actor, 'import.create', str(batch_id), {
            'channel': data.channel, 'filename': data.filename, 'checksum': checksum,
            'rows_total': len(rows), 'rows_inserted': inserted, 'rows_duplicate': duplicate,
            'rows_unresolved': unresolved})
        cursor.execute('SELECT * FROM import_batches WHERE id=%s', (batch_id,))
        batch = cursor.fetchone()
    return {'batch': batch, 'replayed': False, 'issues': []}


def batches():
    with database() as cursor:
        cursor.execute('SELECT * FROM import_batches ORDER BY id DESC LIMIT 50')
        return cursor.fetchall()


def create_record(data, actor):
    try:
        with database() as cursor:
            cursor.execute('INSERT INTO return_records(channel,station_code,day,hour,quantity,source) '
                           'VALUES(%s,%s,%s,%s,%s,%s)',
                           (Channel.MANUAL, data.station_code, data.day, data.hour, data.quantity, data.source))
            record_id = cursor.lastrowid
            audit(cursor, actor, 'record.create', str(record_id), data.model_dump(mode='json'))
    except IntegrityError as error:
        if error.args[0] == 1062:
            raise HTTPException(409, '人工台账下该站点日期和小时已有记录，请直接在校正中修改') from error
        if error.args[0] == 1452:
            raise HTTPException(422, '站点尚未登记') from error
        raise
    return {**data.model_dump(), 'id': record_id, 'revision': 1}


def correct_record(record_id, data, actor):
    """校正一条记录；导入行缺站点或日期时，可在这里补齐落位。"""
    with database() as cursor:
        cursor.execute('SELECT * FROM return_records WHERE id=%s FOR UPDATE', (record_id,))
        before = cursor.fetchone()
        if not before:
            raise HTTPException(404, '归还记录不存在')
        if before['revision'] != data.revision:
            raise HTTPException(409, '有其他同事更新了这条记录，请刷新台账后再校正')
        if data.station_code and data.station_code != before['station_code']:
            cursor.execute('SELECT 1 FROM stations WHERE code=%s', (data.station_code,))
            if not cursor.fetchone():
                raise HTTPException(422, '站点尚未登记')
        updated = {
            'station_code': data.station_code or before['station_code'],
            'day': data.day or before['day'],
            'hour': data.hour if data.hour is not None else before['hour'],
            'quantity': data.quantity if data.quantity is not None else before['quantity'],
            'source': data.source if data.source is not None else before['source'],
        }
        try:
            cursor.execute('UPDATE return_records SET station_code=%s,day=%s,hour=%s,quantity=%s,source=%s,'
                           'revision=revision+1 WHERE id=%s',
                           (updated['station_code'], updated['day'], updated['hour'], updated['quantity'],
                            updated['source'], record_id))
        except IntegrityError as error:
            if error.args[0] == 1062:
                raise HTTPException(409, '同通道下该站点日期小时已有另一条记录，请先合并') from error
            raise
        cursor.execute('SELECT * FROM return_records WHERE id=%s', (record_id,))
        after = cursor.fetchone()
        audit(cursor, actor, 'record.correct', str(record_id), {
            'old': {key: str(before[key]) if before[key] is not None else None
                    for key in ('station_code', 'day', 'hour', 'quantity', 'source')},
            'new': {key: str(after[key]) if after[key] is not None else None
                    for key in ('station_code', 'day', 'hour', 'quantity', 'source')},
        })
        return after
