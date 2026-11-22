from src.utils.serialize import canonical


def stations(cursor):
    cursor.execute('SELECT * FROM stations ORDER BY code')
    return cursor.fetchall()


def list_records(cursor, period, station_code, page):
    where = 'r.day BETWEEN %s AND %s'
    args = [period.start, period.end]
    if station_code:
        where += ' AND r.station_code = %s'
        args.append(station_code)
    cursor.execute(f'SELECT COUNT(*) AS total, COALESCE(SUM(r.quantity),0) AS quantity '
                   f'FROM return_records r WHERE {where}', args)
    totals = cursor.fetchone()
    cursor.execute(f'SELECT r.*, s.name FROM return_records r JOIN stations s '
                   f'ON r.station_code=s.code WHERE {where} '
                   'ORDER BY r.day DESC, r.station_code, r.hour LIMIT 12 OFFSET %s',
                   [*args, (page - 1) * 12])
    return {**totals, 'page': page, 'items': cursor.fetchall()}


def audit(cursor, actor, action, entity_key, payload):
    cursor.execute('INSERT INTO audit_events(actor,action,entity_key,payload) VALUES(%s,%s,%s,%s)',
                   (actor, action, entity_key, canonical(payload)))
