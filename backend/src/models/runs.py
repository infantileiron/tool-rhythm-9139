import json


SUMMARY = 'id,title,creator,status,checksum,created_at,published_at'


def list_runs(cursor, published_only):
    predicate = "WHERE status='published'" if published_only else ''
    cursor.execute(f'SELECT {SUMMARY} FROM runs {predicate} ORDER BY id DESC LIMIT 100')
    return cursor.fetchall()


def run_record(cursor, run_id, *, lock=False):
    lock_clause = 'FOR UPDATE' if lock else ''
    cursor.execute(f'SELECT * FROM runs WHERE id=%s {lock_clause}', (run_id,))
    row = cursor.fetchone()
    if row:
        for key in ('snapshot', 'result', 'decision'):
            if row[key] is not None:
                row[key] = json.loads(row[key])
    return row
