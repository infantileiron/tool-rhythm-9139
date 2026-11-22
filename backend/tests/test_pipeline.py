"""离线跑通演示剧本：两路联单解析 → 逐站对账 → 分型。

不连数据库，只复用 seed 生成的联单与纯计算模块，验证台账数字和分型状态。
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_demo import SITES, batches  # noqa: E402
from src.constants.domain import ALGORITHM, BANDS, ReconState, StationStatus  # noqa: E402
from src.services.classifier import classify  # noqa: E402
from src.services.reconcile import parse_csv, reconcile  # noqa: E402

FAILS = []


def check(name, condition, detail=''):
    print(('ok   ' if condition else 'FAIL ') + name + ('' if condition else f' {detail}'))
    if not condition:
        FAILS.append(name)


def build():
    sites = [{'code': site[0], 'name': site[1]} for site in SITES]
    records, next_id = [], 1

    def add(channel, row, batch_id, filename):
        nonlocal next_id
        records.append({'id': next_id, 'channel': channel, 'station_code': row['station_code'],
                        'day': row['day'], 'hour': row['hour'], 'quantity': row['quantity'],
                        'source': row.get('source') or filename, 'batch_id': batch_id,
                        'row_no': row.get('row_no')})
        next_id += 1

    # 剧本第 3 步：X01 于 11-15 08:00 按复点校正为 8 件（人工记录 R2）。
    add('manual', {'station_code': 'X01', 'day': '2026-11-15', 'hour': 8, 'quantity': 8},
        0, '回收联_1115复点.csv')
    for batch_id, (channel, filename, content, defaults) in enumerate(batches(), start=1):
        rows, issues = parse_csv(content, channel, period_start=date(2026, 11, 9),
                                 period_end=date(2026, 11, 15), **defaults)
        assert not issues, (filename, issues)
        for row in rows:
            add(channel, row, batch_id, filename)
    return sites, records


def main():
    sites, records = build()
    ledger = reconcile(records, sites)
    table = ledger['stations']
    check('X01 补录复点后实收 108', table['X01']['actual'] == 108, table['X01']['actual'])
    check('X01 有未落位纸联仍可部分对上', table['X01']['state'] == ReconState.PARTIAL, table['X01']['state'])
    check('X01 未落位记录保留追溯', len(table['X01']['unresolved']) == 2, table['X01']['unresolved'])
    check('两路重复登记只计一次', table['X02']['actual'] == 70 and
          sum(1 for slot in table['X02']['slots'] if slot['state'].value == 'paired') == 4,
          table['X02']['actual'])
    check('重复行不重复计件', all(slot['actual'] == slot['cabinet'] for slot in table['X02']['slots']
                            if slot['cabinet'] and slot['paper']), table['X02']['slots'][:2])
    check('X11 只有纸联、3 件', table['X11']['actual'] == 3, table['X11'])
    check('X03 争议取小计入实收', table['X03']['actual'] == 197 and table['X03']['disputed'] == 3,
          (table['X03']['actual'], table['X03']['disputed']))
    check('争议站仍可部分对上', table['X03']['state'] == ReconState.PARTIAL, table['X03']['state'])
    check('X12 无记录', table['X12']['state'] == ReconState.NO_DATA, table['X12']['state'])
    check('X13 缺日期纸联无法分型', table['X13']['state'] == ReconState.UNRECONCILED
          and table['X13']['actual'] == 0, table['X13'])
    check('X13 两行待落位', len(table['X13']['unresolved']) == 2, table['X13']['unresolved'])
    check('总实收等于各站实收之和',
          ledger['stats']['records'] == len(records), ledger['stats'])
    check('没有无法归属的记录', not ledger['unattributed'], ledger['unattributed'])

    snapshot = {'algorithm': ALGORITHM, 'bands': BANDS,
                'params': {'eps': 0.035, 'min_points': 3, 'min_returns': 30},
                'stations': [{'code': site['code'], 'name': site['name'],
                              'counts': table[site['code']]['counts'],
                              'actual': table[site['code']]['actual'],
                              'disputed': table[site['code']]['disputed'],
                              'credential': table[site['code']]['credential'],
                              'recon_state': table[site['code']]['state'],
                              'recon_refs': [r['id'] for r in table[site['code']]['records']],
                              'unresolved_refs': [r['id'] for r in table[site['code']]['unresolved']]}
                             for site in sites]}
    result = classify(snapshot)
    members = {m['code']: m for m in result['members']}
    groups = {group['key']: group for group in result['groups']}
    check('形成三个组', len(result['groups']) == 3, [(g['key'], g['station_codes']) for g in result['groups']])
    check('X10 失群', members['X10']['status'] == StationStatus.NOISE, members['X10']['status'])
    check('X11 低样本', members['X11']['status'] == StationStatus.LOW, members['X11']['status'])
    check('X12 无记录', members['X12']['status'] == StationStatus.EMPTY, members['X12']['status'])
    check('X13 未对账不进分组', members['X13']['status'] == StationStatus.UNRECONCILED
          and members['X13']['group'] is None, members['X13'])
    check('X01 归入早间组', members['X01']['group'] == 'G01', members['X01']['group'])
    check('组画像六段', all(len(group['profile']) == 6 for group in groups.values()))
    check('组件数等于成员实收之和',
          all(group['returns'] == sum(members[code]['total'] for code in group['station_codes'])
              for group in result['groups']))
    print('\n分组：', {key: (group['station_codes'], group['returns']) for key, group in groups.items()})
    print('诊断：', result['diagnostics'])
    if FAILS:
        print('\n失败：', '、'.join(FAILS))
        raise SystemExit(1)
    print('\n演示剧本离线复算通过')


if __name__ == '__main__':
    main()
