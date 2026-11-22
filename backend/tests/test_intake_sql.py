"""用内存假游标跑通导入、重放、冲突与对账视图，验证 SQL 与列名和迁移一致。"""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.models.ledger as ledger_model  # noqa: E402
import src.services.intake as intake  # noqa: E402
from src.schemas.inputs import ImportInput, Period  # noqa: E402
from src.utils.serialize import fingerprint  # noqa: E402

FAILS = []


def check(name, condition, detail=''):
    print(('ok   ' if condition else 'FAIL ') + name + ('' if condition else f' {detail}'))
    if not condition:
        FAILS.append(name)


class FakeCursor:
    def __init__(self, tables):
        self.tables = tables
        self.lastrowid = 0
        self._rows = []
        self.connection = None

    # --- 结果集 -------------------------------------------------------------
    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    # --- SQL 分派 -----------------------------------------------------------
    def execute(self, sql, args=None):
        args = list(args or [])
        text = re.sub(r'\s+', ' ', sql).strip()
        self._rows = []
        if text.startswith('SELECT * FROM import_batches WHERE checksum'):
            self._rows = [b for b in self.tables['import_batches'] if b['checksum'] == args[0]]
        elif text.startswith('SELECT * FROM import_batches WHERE id'):
            self._rows = [b for b in self.tables['import_batches'] if b['id'] == args[0]]
        elif text.startswith('SELECT code FROM stations WHERE code IN'):
            wanted = set(args)
            self._rows = [{'code': s['code']} for s in self.tables['stations'] if s['code'] in wanted]
        elif text.startswith('SELECT quantity,batch_id,row_no FROM return_records'):
            channel, station, day, hour = args
            self._rows = [{'quantity': r['quantity'], 'batch_id': r['batch_id'], 'row_no': r['row_no']}
                          for r in self.tables['return_records']
                          if r['channel'] == channel and r['station_code'] == station
                          and str(r['day']) == str(day) and r['hour'] == hour]
        elif text.startswith('SELECT station_code,day,hour,quantity,batch_id,row_no FROM return_records'):
            channel, start, end, *codes = args
            start, end = date.fromisoformat(start), date.fromisoformat(end)
            self._rows = [{'station_code': r['station_code'], 'day': r['day'], 'hour': r['hour'],
                           'quantity': r['quantity'], 'batch_id': r['batch_id'], 'row_no': r['row_no']}
                          for r in self.tables['return_records']
                          if r['channel'] == channel and r['station_code'] in codes
                          and isinstance(r['day'], str) and start <= date.fromisoformat(r['day']) <= end]
        elif text.startswith('INSERT INTO import_batches'):
            self.lastrowid = self.tables['next_batch']
            self.tables['next_batch'] += 1
            (channel, filename, checksum, start, end, actor, total) = args
            self.tables['import_batches'].append({
                'id': self.lastrowid, 'channel': channel, 'filename': filename, 'checksum': checksum,
                'period_start': start, 'period_end': end, 'actor': actor, 'rows_total': total,
                'rows_inserted': 0, 'rows_duplicate': 0, 'rows_unresolved': 0})
        elif text.startswith('UPDATE import_batches SET rows_inserted'):
            inserted, duplicate, unresolved, batch_id = args
            for batch in self.tables['import_batches']:
                if batch['id'] == batch_id:
                    batch.update(rows_inserted=inserted, rows_duplicate=duplicate,
                                 rows_unresolved=unresolved)
        elif text.startswith('INSERT INTO return_records'):
            channel, station, day, hour, quantity, source, batch_id, row_no = args
            for record in self.tables['return_records']:
                if (record['channel'], record['station_code'], record['day'], record['hour']) == (
                        channel, station, day, hour) and station is not None and day is not None:
                    raise Exception(1062, 'Duplicate entry')
            self.tables['return_records'].append({
                'id': self.tables['next_record'], 'channel': channel, 'station_code': station,
                'day': day, 'hour': hour, 'quantity': quantity, 'source': source,
                'batch_id': batch_id, 'row_no': row_no, 'revision': 1})
            self.tables['next_record'] += 1
        elif text.startswith('INSERT INTO audit_events'):
            self.tables['audit_events'].append(args)
        elif text.startswith('SELECT * FROM stations ORDER BY code'):
            self._rows = sorted(self.tables['stations'], key=lambda site: site['code'])
        elif text.startswith('SELECT r.*, b.period_start, b.period_end, b.filename FROM return_records r'):
            start, end, end2, start2 = args
            rows = []
            for record in self.tables['return_records']:
                batch = next((b for b in self.tables['import_batches']
                              if b['id'] == record['batch_id']), None)
                day = record['day']
                day = date.fromisoformat(day) if isinstance(day, str) else day
                placed = day is not None and start <= day <= end
                loose = (record['day'] is None and batch is not None
                         and start2 >= batch['period_start'] and end2 <= batch['period_end'])
                if placed or loose:
                    rows.append({**record, 'period_start': batch['period_start'] if batch else None,
                                 'period_end': batch['period_end'] if batch else None,
                                 'filename': batch['filename'] if batch else None})
            self._rows = rows
        else:
            raise AssertionError(f'未覆盖的 SQL: {text[:90]}')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_database(tables):
    class Context:
        def __enter__(self):
            return FakeCursor(tables)

        def __exit__(self, *exc):
            return False
    return lambda: Context()


def setup():
    tables = {'stations': [{'code': code, 'name': code} for code in ('X01', 'X02')],
              'import_batches': [], 'return_records': [], 'audit_events': [],
              'next_batch': 1, 'next_record': 1}
    context = fake_database(tables)
    intake.database = context
    ledger_model.database = context
    return tables


def payload(channel, content, **extra):
    return ImportInput(channel=channel, filename=f'{channel}.csv', content=content,
                       start=date(2026, 11, 9), end=date(2026, 11, 15), **extra)


def main():
    tables = setup()
    cabinet = '站点,日期,小时,件数,联单\nX01,2026-11-09,8,5,回收联_1109.csv\nX02,2026-11-09,8,3,回收联_1109.csv\n'
    first = intake.import_batch(payload('cabinet', cabinet), 'analyst')
    check('首次导入插入两行', first['batch']['rows_inserted'] == 2 and len(tables['return_records']) == 2,
          first)
    replay = intake.import_batch(payload('cabinet', cabinet), 'analyst')
    check('相同内容重放不新增', replay['replayed'] and len(tables['return_records']) == 2, replay)
    intake.import_batch(payload('cabinet', cabinet), 'analyst')
    check('重放时台账不重复计件', len(tables['return_records']) == 2, len(tables['return_records']))

    partial = '站点,日期,小时,件数,联单\nX01,2026-11-09,8,5,补传.csv\n'
    overlap = intake.import_batch(payload('cabinet', partial), 'analyst')
    check('同槽同件数视为重复行', overlap['batch']['rows_duplicate'] == 1 and
          overlap['batch']['rows_inserted'] == 0, overlap)

    clash = '站点,日期,小时,件数,联单\nX01,2026-11-09,8,9,补传.csv\n'
    try:
        intake.import_batch(payload('cabinet', clash), 'analyst')
        check('同槽不同件数整批拒绝', False, '未抛错')
    except Exception as error:
        check('同槽不同件数整批拒绝', '不同件数' in str(error), error)
    check('拒绝后不落批次', len(tables['import_batches']) == 2, len(tables['import_batches']))

    paper = '小时,件数\n9,7\n16,3\n'
    loose = intake.import_batch(payload('paper', paper, default_station='X01'), 'analyst')
    check('纸联缺日期保留为待落位', loose['batch']['rows_unresolved'] == 2 and
          loose['batch']['rows_inserted'] == 2, loose)
    check('待落位行无日期', all(r['day'] is None for r in tables['return_records'] if r['channel'] == 'paper'))

    try:
        intake.import_batch(payload('paper', '小时,件数\n9,7\n', default_station='X99'), 'analyst')
        check('未知站点整批拒绝', False, '未抛错')
    except Exception as error:
        check('未知站点整批拒绝', '尚未登记' in str(error), error)

    bad = '小时,件数\n9,7\n99,3\n'
    try:
        intake.import_batch(payload('paper', bad), 'analyst')
        check('坏行整批拒绝并给行号', False, '未抛错')
    except Exception as error:
        check('坏行整批拒绝并给行号', '第 3 行' in str(error), error)

    view = intake.reconciliation_view(Period(start=date(2026, 11, 9), end=date(2026, 11, 15)), 'X01')
    detail = view['detail']
    check('对账视图带出站点', {site['code'] for site in view['stations']} == {'X01', 'X02'}, view['stations'])
    check('X01 实收 5、两条待落位', detail['actual'] == 5 and len(detail['unresolved']) == 2,
          (detail['actual'], len(detail['unresolved'])))
    check('X01 状态为部分对上', detail['state'] == 'partial', detail['state'])
    check('未落位计数进统计', view['stats']['unresolved_rows'] == 2, view['stats'])

    import src.services.plans as plans
    from src.schemas.inputs import PlanInput
    context = fake_database(tables)
    plans.database = context
    params = PlanInput(title='演示', start=date(2026, 11, 9), end=date(2026, 11, 15),
                       eps=0.035, min_points=3, min_returns=30)
    with context() as cursor:
        snap_a = plans.snapshot(cursor, params)
        snap_b = plans.snapshot(cursor, params)
    check('相同快照相同指纹', fingerprint(snap_a) == fingerprint(snap_b))
    x01 = next(site for site in snap_a['stations'] if site['code'] == 'X01')
    known = {record['id'] for record in tables['return_records']}
    check('快照记录引用可回溯', set(x01['recon_refs']) | set(x01['unresolved_refs']) <= known,
          (x01['recon_refs'], x01['unresolved_refs']))
    check('快照计入实收与对账状态', x01['actual'] == 5 and x01['recon_state'] == 'partial', x01)
    check('快照算法标识', snap_a['algorithm'] == 'cosine-dbscan-v2', snap_a['algorithm'])

    if FAILS:
        print('\n失败：', '、'.join(FAILS))
        raise SystemExit(1)
    print('\n导入与对账视图 SQL 冒烟通过')


if __name__ == '__main__':
    main()
