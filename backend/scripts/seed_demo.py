import json

from src.config.database import database
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
]
DAYS = ['2026-11-09', '2026-11-12', '2026-11-15']
HOURS = [7, 10, 12, 15, 18, 22]


def seed():
    with database() as cursor:
        cursor.executemany('INSERT INTO users(username,display_name,role,password_hash) '
                           'VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE username=username',
                           [(*user, hash_password('Workbench-5206')) for user in USERS])
        cursor.executemany('INSERT INTO stations(code,name,address,steward) VALUES(%s,%s,%s,%s) '
                           'ON DUPLICATE KEY UPDATE code=code', [site[:4] for site in SITES])
        rows = []
        for code, _, _, _, distribution in SITES:
            for hour, total in zip(HOURS, distribution):
                base, remainder = divmod(total, len(DAYS))
                for index, day in enumerate(DAYS):
                    quantity = base + (index < remainder)
                    if quantity:
                        rows.append((code, day, hour, quantity, f'回收联_{day[5:].replace("-", "")}.csv'))
        cursor.executemany('INSERT INTO return_records(station_code,day,hour,quantity,source) '
                           'VALUES(%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE id=id', rows)
        tables = {'users': ('username',), 'stations': ('code',),
                  'return_records': ('station_code', 'day', 'hour')}
        summary = {}
        for table, fields in tables.items():
            columns = ','.join(fields)
            cursor.execute(f'SELECT {columns} FROM {table} ORDER BY {columns}')
            keys = [[str(row[field]) for field in fields] for row in cursor.fetchall()]
            summary[table] = {'count': len(keys), 'natural_keys_sha256': fingerprint(keys)}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    seed()
