from fastapi import HTTPException
from pymysql.err import IntegrityError

from src.config.database import database
from src.models.ledger import audit, list_records, stations


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


def records(period, station_code, page):
    with database() as cursor:
        return list_records(cursor, period, station_code, page)


def create_record(data, actor):
    try:
        with database() as cursor:
            cursor.execute('INSERT INTO return_records(station_code,day,hour,quantity,source) '
                           'VALUES(%s,%s,%s,%s,%s)',
                           (data.station_code, data.day, data.hour, data.quantity, data.source))
            record_id = cursor.lastrowid
            audit(cursor, actor, 'record.create', str(record_id), data.model_dump(mode='json'))
    except IntegrityError as error:
        if error.args[0] == 1062:
            raise HTTPException(409, '该站点日期和小时已有记录，可在台账中校正') from error
        if error.args[0] == 1452:
            raise HTTPException(422, '站点尚未登记') from error
        raise
    return {**data.model_dump(), 'id': record_id, 'revision': 1}


def correct_record(record_id, data, actor):
    with database() as cursor:
        cursor.execute('SELECT * FROM return_records WHERE id=%s FOR UPDATE', (record_id,))
        before = cursor.fetchone()
        if not before:
            raise HTTPException(404, '归还记录不存在')
        if before['revision'] != data.revision:
            raise HTTPException(409, '有其他同事更新了这条记录，请刷新台账后再校正')
        cursor.execute('UPDATE return_records SET quantity=%s,source=%s,revision=revision+1 WHERE id=%s',
                       (data.quantity, data.source, record_id))
        audit(cursor, actor, 'record.correct', str(record_id), {
            'old': {'quantity': before['quantity'], 'source': before['source']},
            'new': data.model_dump(),
        })
        return {**before, 'quantity': data.quantity, 'source': data.source, 'revision': data.revision + 1}
