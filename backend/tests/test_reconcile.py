"""离线复算：两路联单解析、逐站对账、分型门槛。仅依赖标准库与 pydantic 之外纯计算模块。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants.domain import ReconState, RecordState, StationStatus  # noqa: E402
from src.services.classifier import classify  # noqa: E402
from src.services.reconcile import parse_csv, reconcile  # noqa: E402

FAILS = []


def check(name, condition, detail=''):
    if condition:
        print(f'ok   {name}')
    else:
        FAILS.append(f'{name} {detail}')
        print(f'FAIL {name} {detail}')


def test_parse_day_variants():
    rows, issues = parse_csv(
        '日期,小时,件数\n2026-11-09,8,5\n20261112,9,4\n2026年11月15日,10,3\n'
        '11月12日,11,2\n2026/11/09,12:00,1\n',
        'cabinet', default_station='X01', period_start=date(2026, 11, 9), period_end=date(2026, 11, 15))
    check('解析多种日期写法', not issues and len(rows) == 5, issues)
    check('解析冒号小时', rows[-1]['hour'] == 12 and rows[-1]['quantity'] == 1, rows[-1])
    check('默认站点补齐', all(row['station_code'] == 'X01' for row in rows))


def test_parse_headerless():
    rows, issues = parse_csv('10,7\n18,3\n', 'paper')
    check('无表头两列按 小时,件数', not issues and rows == [
        {'station_code': None, 'day': None, 'hour': 10, 'quantity': 7, 'source': None, 'row_no': 1},
        {'station_code': None, 'day': None, 'hour': 18, 'quantity': 3, 'source': None, 'row_no': 2},
    ], (rows, issues))


def test_parse_rejects_whole_batch():
    _, issues = parse_csv('小时,件数\n8,5\n99,3\n', 'paper')
    check('坏行整批拒绝并报行号', issues and '第 3 行' in issues[0], issues)
    _, issues = parse_csv('小时,件数\n8,0\n', 'paper')
    check('零件被拒绝', issues and '1–9999' in issues[0], issues)
    _, issues = parse_csv('小时,件数\n8,3\n', 'paper', period_start=date(2026, 11, 9),
                          period_end=date(2026, 11, 15), default_day=date(2026, 12, 1))
    check('默认日期越窗被拒绝', issues and '窗口' in issues[0], issues)


def record(rid, channel, station, day, hour, quantity, batch_id=1):
    return {'id': rid, 'channel': channel, 'station_code': station, 'day': day, 'hour': hour,
            'quantity': quantity, 'source': 's', 'batch_id': batch_id, 'row_no': rid}


def test_reconcile_core():
    sites = [{'code': code, 'name': code} for code in ('X01', 'X02', 'X03', 'X04', 'X05', 'X06')]
    records = [
        # X01：柜机 8、纸联 8 → 成对只计一次 8
        record(1, 'cabinet', 'X01', '2026-11-09', 8, 8),
        record(2, 'paper', 'X01', '2026-11-09', 8, 8),
        # X02：柜机 6、纸联 2 → 实收 2，争议 4，凭证 6，争议占比 2/3 → 未对账
        record(3, 'cabinet', 'X02', '2026-11-09', 10, 6),
        record(4, 'paper', 'X02', '2026-11-09', 10, 2),
        # X03：只有柜机 → 单边实收
        record(5, 'cabinet', 'X03', '2026-11-09', 15, 30),
        # X04：人工记录覆盖导入，导入行不重复计件
        record(6, 'manual', 'X04', '2026-11-09', 12, 5),
        record(7, 'cabinet', 'X04', '2026-11-09', 12, 5),
        # X05：缺日期的纸联 → 未落位，实收 0 → 未对账
        record(8, 'paper', 'X05', None, 9, 4),
        # X06：柜机 10、纸联 10（成对），另有一条缺日期纸联，实收仍可用 → 部分对上
        record(9, 'cabinet', 'X06', '2026-11-09', 18, 10),
        record(10, 'paper', 'X06', '2026-11-09', 18, 10),
        record(11, 'paper', 'X06', None, 19, 3),
        # 未登记站点的记录
        record(12, 'cabinet', 'X99', '2026-11-09', 8, 2),
    ]
    ledger = reconcile(records, sites)
    stations = ledger['stations']
    check('成对槽只计一次', stations['X01']['actual'] == 8 and stations['X01']['disputed'] == 0,
          stations['X01'])
    check('成对记录标 paired',
          {r['state'] for r in stations['X01']['records']} == {RecordState.PAIRED},
          stations['X01']['records'])
    check('差异槽取小计入实收', stations['X02']['actual'] == 2 and stations['X02']['disputed'] == 4,
          stations['X02'])
    check('争议过半转未对账', stations['X02']['state'] == ReconState.UNRECONCILED, stations['X02']['state'])
    check('单边柜机实收', stations['X03']['actual'] == 30 and stations['X03']['state'] == ReconState.CLEAN,
          stations['X03'])
    check('人工记录覆盖导入且导入标重复',
          stations['X04']['actual'] == 5 and
          any(r['state'] == RecordState.DUPLICATE for r in stations['X04']['records']),
          stations['X04']['records'])
    check('缺日期纸联未落位', stations['X05']['state'] == ReconState.UNRECONCILED and
          stations['X05']['unresolved'][0]['reason'] == 'no_day', stations['X05'])
    check('少量未落位仍可部分对上', stations['X06']['state'] == ReconState.PARTIAL, stations['X06'])
    check('未登记站点单独列出',
          ledger['unattributed'][0]['station_code'] == 'X99' and
          ledger['unattributed'][0]['reason'] == 'unknown_station', ledger['unattributed'])
    check('统计重复行', ledger['stats']['duplicate_rows'] == 1, ledger['stats'])


def test_classify_gate():
    def site(code, counts, state, actual=None):
        return {'code': code, 'name': code, 'counts': counts, 'recon_state': state,
                'actual': sum(counts) if actual is None else actual,
                'disputed': 0, 'credential': sum(counts)}

    snapshot = {
        'algorithm': 'cosine-dbscan-v2',
        'bands': [(0, 8), (8, 11), (11, 14), (14, 17), (17, 20), (20, 24)],
        'params': {'eps': 0.035, 'min_points': 3, 'min_returns': 30},
        'stations': [
            site('X01', [1, 60, 5, 1, 1, 1], ReconState.CLEAN),
            site('X02', [1, 55, 6, 1, 1, 1], ReconState.CLEAN),
            site('X03', [1, 52, 8, 1, 1, 1], ReconState.CLEAN),
            site('X04', [1, 50, 7, 1, 1, 1], ReconState.PARTIAL),
            site('X05', [0, 0, 0, 0, 0, 0], ReconState.NO_DATA),
            site('X06', [0, 9, 0, 0, 0, 0], ReconState.UNRECONCILED),
            site('X07', [0, 9, 0, 0, 0, 0], ReconState.CLEAN),
            site('X08', [1, 1, 1, 60, 1, 1], ReconState.CLEAN),
        ]}
    result = classify(snapshot)
    members = {m['code']: m for m in result['members']}
    check('未对账站不进分型', members['X06']['status'] == StationStatus.UNRECONCILED and
          members['X06']['group'] is None, members['X06'])
    check('无记录站标无记录', members['X05']['status'] == StationStatus.EMPTY, members['X05'])
    check('部分对上照常分型', members['X04']['group'] == members['X01']['group'], members['X04'])
    check('失群站保留诊断', members['X08']['status'] == StationStatus.NOISE, members['X08'])
    check('低于门槛标低样本', members['X07']['status'] == StationStatus.LOW, members['X07'])
    check('四站成组', members['X01']['group'] == members['X02']['group'] == members['X03']['group'],
          {code: members[code]['group'] for code in ('X01', 'X02', 'X03', 'X04')})
    check('分组画像仍为等权', len(next(g for g in result['groups'] if g['key'] == 'G01')['profile']) == 6)
    check('诊断统计未对账数', result['diagnostics']['unreconciled'] == 1, result['diagnostics'])
    check('空合格集产出零组', classify({**snapshot, 'stations': [
        site('X06', [0, 9, 0, 0, 0, 0], ReconState.UNRECONCILED)]})['groups'] == [])


if __name__ == '__main__':
    test_parse_day_variants()
    test_parse_headerless()
    test_parse_rejects_whole_batch()
    test_reconcile_core()
    test_classify_gate()
    if FAILS:
        print('\n失败：')
        for fail in FAILS:
            print(' -', fail)
        raise SystemExit(1)
    print('\n全部通过')
