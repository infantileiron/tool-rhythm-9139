from src.utils.serialize import canonical


def stations(cursor):
    cursor.execute('SELECT * FROM stations ORDER BY code')
    return cursor.fetchall()


def records_in_window(cursor, start, end):
    """窗口内的台账记录。

    无日期的纸联行按其所属导入批次窗口归属到本次计算，避免永久阻断分型；
    人工校正过日期或补齐站点后，行会随新版本生效。
    """
    cursor.execute('SELECT r.*, b.period_start, b.period_end, b.filename '
                   'FROM return_records r LEFT JOIN import_batches b ON r.batch_id=b.id '
                   'WHERE (r.day BETWEEN %s AND %s) '
                   '   OR (r.day IS NULL AND b.id IS NOT NULL AND b.period_start <= %s AND b.period_end >= %s) '
                   'ORDER BY r.station_code, r.day, r.hour, r.channel, r.id',
                   (start, end, end, start))
    return cursor.fetchall()


def records_by_ids(cursor, ids):
    if not ids:
        return []
    placeholders = ','.join(['%s'] * len(ids))
    cursor.execute(f'SELECT r.* FROM return_records r WHERE r.id IN ({placeholders}) '
                   'ORDER BY r.station_code, r.day, r.hour, r.channel, r.id', ids)
    return cursor.fetchall()


def list_records(cursor, period, station_code, channel, page, size=12):
    where = ["((r.day BETWEEN %s AND %s) OR (r.day IS NULL AND b.id IS NOT NULL "
             "AND b.period_start <= %s AND b.period_end >= %s))"]
    args = [period.start, period.end, period.end, period.start]
    if station_code:
        where.append('r.station_code = %s')
        args.append(station_code)
    if channel:
        where.append('r.channel = %s')
        args.append(channel)
    clause = ' AND '.join(where)
    cursor.execute(f'SELECT COUNT(*) AS total, COALESCE(SUM(r.quantity),0) AS quantity, '
                   f'COALESCE(SUM(r.station_code IS NULL OR r.day IS NULL),0) AS unresolved '
                   f'FROM return_records r LEFT JOIN import_batches b ON r.batch_id=b.id WHERE {clause}', args)
    totals = cursor.fetchone()
    cursor.execute(f'SELECT r.*, s.name, b.filename FROM return_records r '
                   f'LEFT JOIN stations s ON r.station_code=s.code '
                   f'LEFT JOIN import_batches b ON r.batch_id=b.id WHERE {clause} '
                   'ORDER BY r.day IS NULL, r.day DESC, r.station_code, r.hour, r.id '
                   'LIMIT %s OFFSET %s', [*args, size, (page - 1) * size])
    return {**totals, 'page': page, 'size': size, 'items': cursor.fetchall()}


def audit(cursor, actor, action, entity_key, payload):
    cursor.execute('INSERT INTO audit_events(actor,action,entity_key,payload) VALUES(%s,%s,%s,%s)',
                   (actor, action, entity_key, canonical(payload)))
