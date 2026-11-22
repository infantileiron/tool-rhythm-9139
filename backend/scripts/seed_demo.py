import json
from datetime import date

from src.config.database import database
from src.constants.domain import Channel
from src.services.intake import batch_checksum
from src.services.reconcile import parse_csv
from src.utils.passwords import hash_password
from src.utils.serialize import fingerprint

USERS = [
    ('analyst', '周禾 · 分析员', 'analyst'),
    ('admin', '韩宁 · 值班负责人', 'admin'),
    ('observer', '宋可 · 观察员', 'observer'),
]
SITES = [
    ('X01', '溪口修造站', '溪口街 12 号', '曹琴', [2, 76, 14, 4, 3, 1]),
    ('X02', '柳桥邻里站', '柳桥巷 8 号', '许竹', [1, 50, 12, 3, 3, 1]),
    ('X03', '油坊工具角', '旧油坊 2 幢', '孟璇', [4, 154, 22, 9, 7, 4]),
    ('X04', '南埠修补站', '南埠路 26 号', '邵琳', [2, 8, 17, 64, 7, 2]),
    ('X05', '石板街驿站', '石板街 15 号', '李素', [1, 4, 14, 40, 5, 1]),
    ('X06', '雨棚共享站', '南菜场西门', '杜鸣', [3, 10, 21, 92, 11, 3]),
    ('X07', '棠树里工具柜', '棠树里 1 栋', '何秋', [2, 6, 7, 12, 70, 3]),
    ('X08', '竹径工作间', '竹径支路 19 号', '谢莉', [2, 4, 4, 11, 52, 2]),
    ('X09', '槐影工坊', '槐影坊 3 号', '乔远', [4, 8, 11, 23, 109, 5]),
    ('X10', '北渠夜班柜', '北渠广场东侧', '汪弦', [57, 3, 2, 5, 2, 42]),
    ('X11', '谷场试点站', '旧谷场北门', '孙苇', [0, 2, 1, 0, 0, 0]),
    ('X12', '香樟里预备站', '香樟里 9 号', '叶亭', [0, 0, 0, 0, 0, 0]),
    ('X13', '新桥代收点', '新桥路 4 号', '罗青', [0, 0, 0, 0, 0, 0]),
]
DAYS = ['2026-11-09', '2026-11-12', '2026-11-15']
HOURS = [7, 10, 12, 15, 18, 22]
PERIOD = ('2026-11-09', '2026-11-15')


def split_rows(code, distribution):
    rows = []
    for hour, total in zip(HOURS, distribution):
        base, remainder = divmod(total, len(DAYS))
        for index, day in enumerate(DAYS):
            quantity = base + (index < remainder)
            if quantity:
                rows.append({'station_code': code, 'day': day, 'hour': hour, 'quantity': quantity})
    return rows


def cabinet_csv(rows, day=None):
    lines = ['站点,日期,小时,件数,联单']
    for row in rows:
        if day is None or row['day'] == day:
            lines.append(f"{row['station_code']},{row['day']},{row['hour']},{row['quantity']},"
                         f"回收联_{row['day'][5:].replace('-', '')}.csv")
    return '\n'.join(lines) + '\n'


def plain_csv(rows, source, with_day=True, with_station=True):
    header = ['站点', '日期', '小时', '件数', '联单']
    keep = [with_station, with_day, True, True, True]
    lines = [','.join(name for name, use in zip(header, keep) if use)]
    for row in rows:
        cells = [row['station_code'], row['day'], row['hour'], row['quantity'], source]
        lines.append(','.join(str(cell) for cell, use in zip(cells, keep) if use))
    return '\n'.join(lines) + '\n'


def batches():
    """按演示剧本生成两路联单。返回 (channel, filename, content, defaults)。

    柜机流水覆盖 X01–X10 的三张日联；纸联补齐以下情形，供对账与分型演示：
    与柜机重复登记、复点校正、只剩小时件数的散联、只有纸联的低样本站与无法落位的代收点。
    """
    cabinet_rows = [row for code, *_rest, distribution in SITES[:10]
                    for row in split_rows(code, distribution)]
    out = []
    for day in DAYS:
        out.append((Channel.CABINET, f'回收联_{day[5:].replace("-", "")}.csv',
                    cabinet_csv(cabinet_rows, day), {}))
    # 纸联与柜机流水重复登记的两站：件数相同，对账时只计一次；X03 的 10 点纸联记 48 件，
    # 与柜机 51 件对不上，差额 3 件计入争议、不计实收。
    duplicate = [row for row in cabinet_rows
                 if row['station_code'] in {'X02', 'X04'} and row['day'] == '2026-11-12']
    dispute = [{'station_code': 'X03', 'day': '2026-11-12', 'hour': 10, 'quantity': 48}]
    out.append((Channel.PAPER, '回收联_1112.csv',
                plain_csv(duplicate + dispute, '回收联_1112.csv'), {}))
    # 11-15 08:00 的补录与复点见 seed()：人工记录先记 5 件，再按复点校正为 8 件（R2）。
    # 只剩小时和件数的纸联：缺日期，保留为未落位记录，X01 仍可用柜机实收分型。
    loose = [{'station_code': 'X01', 'day': '', 'hour': 9, 'quantity': 7},
             {'station_code': 'X01', 'day': '', 'hour': 16, 'quantity': 3}]
    out.append((Channel.PAPER, '纸联_X01_零散.csv',
                plain_csv(loose, '纸联_X01_零散.csv', with_day=False), {'default_station': 'X01'}))
    # 谷场试点站只有纸联、件数低于门槛。
    low = [{'station_code': 'X11', 'day': day, 'hour': hour, 'quantity': quantity}
           for day, hour, quantity in (('2026-11-09', 10, 2), ('2026-11-12', 10, 0),
                                       ('2026-11-15', 12, 1)) if quantity]
    out.append((Channel.PAPER, '纸联_X11.csv', plain_csv(low, '纸联_X11.csv'), {}))
    # 新桥代收点只有缺日期的纸联，没有任何可计入实收，无法分型。
    stub = [{'station_code': 'X13', 'day': '', 'hour': 10, 'quantity': 4},
            {'station_code': 'X13', 'day': '', 'hour': 18, 'quantity': 6}]
    out.append((Channel.PAPER, '纸联_X13_代收.csv',
                plain_csv(stub, '纸联_X13_代收.csv', with_day=False), {'default_station': 'X13'}))
    return out


def seed():
    with database() as cursor:
        cursor.executemany('INSERT INTO users(username,display_name,role,password_hash) '
                           'VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE username=username',
                           [(*user, hash_password('Workbench-5206')) for user in USERS])
        cursor.executemany('INSERT INTO stations(code,name,address,steward) VALUES(%s,%s,%s,%s) '
                           'ON DUPLICATE KEY UPDATE code=code', [site[:4] for site in SITES])
        # 剧本第 3 步：X01 于 11-15 08:00 先补录 5 件，再按纸联复点校正为 8 件（R2）。
        cursor.execute('INSERT INTO return_records(channel,station_code,day,hour,quantity,source,revision) '
                       "VALUES('manual','X01','2026-11-15',8,8,'回收联_1115复点.csv',2) "
                       'ON DUPLICATE KEY UPDATE id=id')
        for channel, filename, content, defaults in batches():
            checksum = batch_checksum(channel, content, defaults.get('default_station'),
                                      defaults.get('default_day'),
                                      date.fromisoformat(PERIOD[0]), date.fromisoformat(PERIOD[1]))
            cursor.execute('SELECT id FROM import_batches WHERE checksum=%s', (checksum,))
            existing = cursor.fetchone()
            if existing:
                continue
            rows, issues = parse_csv(content, channel,
                                     period_start=date.fromisoformat(PERIOD[0]),
                                     period_end=date.fromisoformat(PERIOD[1]), **defaults)
            if issues:
                raise SystemExit(f'演示联单 {filename} 有错误：{issues}')
            cursor.execute('INSERT INTO import_batches(channel,filename,checksum,period_start,period_end,actor,'
                           'rows_total,rows_inserted,rows_duplicate,rows_unresolved) '
                           'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,0,0)',
                           (channel, filename, checksum, PERIOD[0], PERIOD[1], 'analyst', len(rows), len(rows)))
            batch_id = cursor.lastrowid
            unresolved = 0
            for row in rows:
                cursor.execute('INSERT INTO return_records(channel,station_code,day,hour,quantity,source,'
                               'batch_id,row_no) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                               (channel, row['station_code'], row['day'], row['hour'], row['quantity'],
                                row['source'] or filename, batch_id, row['row_no']))
                unresolved += not row['station_code'] or not row['day']
            cursor.execute('UPDATE import_batches SET rows_unresolved=%s WHERE id=%s', (unresolved, batch_id))
        tables = {'users': ('username',), 'stations': ('code',),
                  'import_batches': ('checksum',),
                  'return_records': ('channel', 'station_code', 'day', 'hour')}
        summary = {}
        for table, fields in tables.items():
            columns = ','.join(fields)
            cursor.execute(f'SELECT {columns} FROM {table} ORDER BY {columns}')
            keys = [[str(row[field]) for field in fields] for row in cursor.fetchall()]
            summary[table] = {'count': len(keys), 'natural_keys_sha256': fingerprint(keys)}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    seed()
