from fastapi import HTTPException

from src.config.database import database
from src.middlewares.auth import issue
from src.utils.passwords import hash_password, matches

DUMMY_HASH = hash_password('invalid')


def login(data):
    with database() as cursor:
        cursor.execute('SELECT * FROM users WHERE username=%s', (data.username,))
        user = cursor.fetchone()
    valid = matches(data.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, '账号或密码有误')
    return {'token': issue(user), 'username': user['username'], 'name': user['display_name'], 'role': user['role']}
