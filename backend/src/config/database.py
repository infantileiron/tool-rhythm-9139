import os
from contextlib import contextmanager

import pymysql


@contextmanager
def database():
    connection = pymysql.connect(
        host=os.environ.get('MYSQL_HOST', 'db'),
        port=int(os.environ.get('MYSQL_PORT', 3306)),
        user=os.environ.get('MYSQL_USER', 'rhythm'),
        password=os.environ['MYSQL_PASSWORD'],
        database=os.environ.get('MYSQL_DATABASE', 'tool_rhythm'),
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=4, read_timeout=10, write_timeout=10,
        init_command="SET time_zone = '+00:00'",
    )
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
