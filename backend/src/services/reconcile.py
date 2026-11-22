"""两路归还联的解析与对账。

柜机流水与纸联都可能记录同一件工具。这里按“站点 / 日 / 小时”槽位把两路记录放到一起：

- 人工台账记录视为已校正的实收，槽位内以它为准，导入行标为重复、不重复计件；
- 柜机与纸联合计同槽且件数相同，视为同一件工具，只计一次；
- 两路件数不同，只取较小的已核件数计入实收，差额作为争议件数，不计实收；
- 只有一路的槽位按单边实收计入，仍可参与分型。

站点层面：
- 完全没有任何记录 → no_data；
- 有记录但全部无从落位（缺站点/日期）或争议件数达到凭证量一半 → unreconciled，
  实收已不能代表该站节律，列为例外，不参与分型；
- 有未落位记录或少量争议，但已对上实收仍达到门槛 → partial，照常分型，
  未对上的记录只在追溯中列出，不进入向量。

全部函数只依赖标准库，便于离线复算。
"""

import csv
import io
import re
from datetime import date

from src.constants.domain import (
    DISPUTE_SHARE,
    Channel,
    RecordState,
    ReconState,
    band_index,
)

STATION_RE = re.compile(r'^[A-Z][A-Z0-9-]{1,11}$')
HEADER_ALIASES = {
    'station': {'站点', '站点编号', '站点编码', 'station', 'station_code', 'code'},
    'day': {'日期', 'date', 'day'},
    'hour': {'小时', 'hour'},
    'quantity': {'件数', '数量', 'quantity', 'qty'},
    'source': {'联单', '来源', 'source'},
}
REQUIRED = ('hour', 'quantity')
HOUR_RE = re.compile(r'^(\d{1,2})(?::\d{2})?时?$')


def parse_day(text, fallback_year):
    value = str(text or '').strip()
    if not value:
        return None
    if re.fullmatch(r'\d{8}', value):
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    for pattern in (r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', r'(\d{4})年(\d{1,2})月(\d{1,2})日?'):
        match = re.fullmatch(pattern, value)
        if match:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.fullmatch(r'(\d{1,2})[-/月](\d{1,2})日?', value)
    if match:
        return date(fallback_year, int(match.group(1)), int(match.group(2)))
    raise ValueError(f'无法识别的日期 {value!r}')


def parse_hour(text):
    match = HOUR_RE.fullmatch(str(text or '').strip())
    if not match:
        raise ValueError(f'无法识别的小时 {text!r}')
    hour = int(match.group(1))
    if not 0 <= hour <= 23:
        raise ValueError(f'小时 {hour} 超出 0–23')
    return hour


def _columns(header):
    mapping = {}
    for index, cell in enumerate(header):
        name = str(cell or '').strip().lower()
        for field, aliases in HEADER_ALIASES.items():
            if name in {alias.lower() for alias in aliases}:
                mapping[field] = index
                break
    return mapping


def _looks_numeric(first, second):
    try:
        parse_hour(first)
        int(second)
        return True
    except (TypeError, ValueError):
        return False


def parse_csv(text, channel, *, default_station=None, default_day=None,
              period_start=None, period_end=None):
    """解析一路归还联。返回 (rows, issues)；有行级错误时整批拒绝。

    允许纸联缺少站点或日期列/单元格，此时使用导入批次的默认站点或默认日期；
    仍缺站点或日期的行会保留为未落位记录，等待人工核对。
    无表头的两列文本按“小时, 件数”读取。
    """
    if channel not in (Channel.CABINET, Channel.PAPER):
        raise ValueError('来源通道只能是 cabinet 或 paper')
    reader = csv.reader(io.StringIO(str(text).lstrip('﻿')))
    lines = [(number, row) for number, row in enumerate(reader, start=1)
             if any(str(cell or '').strip() for cell in row)]
    if not lines:
        raise ValueError('联单为空')
    _, header = lines[0]
    mapping = _columns(header)
    if all(field in mapping for field in REQUIRED):
        body = lines[1:]
    elif _looks_numeric(*(header + [''])[:2]):
        mapping = {'hour': 0, 'quantity': 1}
        body = lines
    else:
        raise ValueError('首行需为表头且至少包含“小时”和“件数”两列')
    fallback_year = (period_start or default_day or date.today()).year
    rows, issues = [], []
    for number, raw in body:
        def cell(field):
            index = mapping.get(field)
            return raw[index].strip() if index is not None and index < len(raw) else ''

        try:
            if not cell('hour') or not cell('quantity'):
                raise ValueError('小时和件数不能为空')
            hour = parse_hour(cell('hour'))
            quantity = int(cell('quantity'))
            if not 1 <= quantity <= 9999:
                raise ValueError(f'件数 {quantity} 超出 1–9999')
            station = (cell('station') or (default_station or '')).strip().upper() or None
            if station and not STATION_RE.match(station):
                raise ValueError(f'站点编号 {station!r} 格式不正确')
            day = parse_day(cell('day'), fallback_year) or default_day
            if day and period_start and period_end and not period_start <= day <= period_end:
                raise ValueError(f'日期 {day} 不在导入窗口内')
            rows.append({'station_code': station, 'day': day.isoformat() if day else None,
                         'hour': hour, 'quantity': quantity,
                         'source': cell('source') or None, 'row_no': number})
        except ValueError as error:
            issues.append(f'第 {number} 行：{error}')
    if issues:
        return [], issues
    return rows, []


def _slot_sum(entries):
    return sum(entry['quantity'] for entry in entries)


def _entry(record):
    day = record.get('day')
    return {'id': record.get('id'), 'channel': record['channel'],
            'day': day.isoformat() if hasattr(day, 'isoformat') else day,
            'hour': int(record['hour']), 'quantity': int(record['quantity']),
            'source': record.get('source'), 'batch_id': record.get('batch_id'),
            'row_no': record.get('row_no'), 'station_code': record.get('station_code')}


def reconcile(records, stations):
    """把窗口内的记录按站点槽位对账。

    records 为台账行（channel 取 manual/cabinet/paper），stations 为站点表行。
    返回逐站实收、争议、槽位与记录追溯，以及无法归属到任何站点的记录。
    """
    known = {site['code']: site for site in stations}
    pods = {code: {'slots': {}, 'unresolved': []} for code in known}
    unattributed = []
    for record in records:
        entry = _entry(record)
        station = entry['station_code']
        if not station or station not in pods:
            entry['state'] = RecordState.UNMATCHED
            entry['reason'] = 'unattributed' if not station else 'unknown_station'
            unattributed.append(entry)
            continue
        if not entry['day']:
            entry['state'] = RecordState.UNMATCHED
            entry['reason'] = 'no_day'
            entry['band'] = band_index(entry['hour'])
            pods[station]['unresolved'].append(entry)
            continue
        slot = pods[station]['slots'].setdefault((entry['day'], entry['hour']),
                                                 {'manual': [], 'cabinet': [], 'paper': []})
        slot.setdefault(entry['channel'], []).append(entry)

    report = {}
    stats = {'records': len(records), 'paired_slots': 0, 'disputed_slots': 0,
             'standalone_slots': 0, 'manual_slots': 0, 'duplicate_rows': 0,
             'unresolved_rows': 0, 'unattributed_rows': len(unattributed)}
    for code, site in known.items():
        pod = pods[code]
        counts = [0] * 6
        actual = disputed = 0
        slots, entries = [], []
        for (day, hour), channels in sorted(pod['slots'].items()):
            manual = channels.get('manual', [])
            cabinet = channels.get('cabinet', [])
            paper = channels.get('paper', [])
            m, c, p = _slot_sum(manual), _slot_sum(cabinet), _slot_sum(paper)
            imported = c + p
            if m:
                state, counted, gap = RecordState.MANUAL, m, 0
                for entry in cabinet + paper:
                    entry['state'] = RecordState.DUPLICATE
                stats['duplicate_rows'] += len(cabinet) + len(paper)
                stats['manual_slots'] += 1
            elif c and p:
                counted, gap = min(c, p), abs(c - p)
                state = RecordState.PAIRED if not gap else RecordState.DISPUTED
                stats['paired_slots' if not gap else 'disputed_slots'] += 1
                for entry in cabinet + paper:
                    entry['state'] = state
            else:
                state, counted, gap = RecordState.STANDALONE, c or p, 0
                stats['standalone_slots'] += 1
                for entry in cabinet + paper:
                    entry['state'] = state
            for entry in manual:
                entry['state'] = RecordState.MANUAL
            actual += counted
            disputed += gap
            counts[band_index(hour)] += counted
            slots.append({'day': day, 'hour': hour, 'state': state,
                          'actual': counted, 'disputed': gap,
                          'manual': m, 'cabinet': c, 'paper': p,
                          'overridden': max(0, imported - m) if m else 0})
            entries.extend(manual + cabinet + paper)
        credential = actual + disputed
        unresolved = pod['unresolved']
        if not slots and not unresolved:
            state = ReconState.NO_DATA
        elif actual == 0:
            state = ReconState.UNRECONCILED
        elif disputed >= DISPUTE_SHARE * credential:
            state = ReconState.UNRECONCILED
        elif unresolved or disputed:
            state = ReconState.PARTIAL
        else:
            state = ReconState.CLEAN
        stats['unresolved_rows'] += len(unresolved)
        entries.sort(key=lambda entry: (entry['day'], entry['hour'], entry['channel'], entry['id'] or 0))
        slots.sort(key=lambda slot: (slot['day'], slot['hour']))
        report[code] = {
            'code': code, 'name': site.get('name'), 'state': state, 'counts': counts,
            'actual': actual, 'disputed': disputed, 'credential': credential,
            'slots': slots, 'records': entries, 'unresolved': unresolved,
        }
    return {'stations': report, 'unattributed': unattributed, 'stats': stats}
