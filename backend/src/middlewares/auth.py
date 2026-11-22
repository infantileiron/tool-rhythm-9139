import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.constants.domain import Role

SECRET = os.environ['JWT_SECRET']
bearer = HTTPBearer(auto_error=False)


def issue(user):
    return jwt.encode({'sub': user['username'], 'role': user['role'], 'name': user['display_name'],
                       'exp': datetime.now(timezone.utc) + timedelta(hours=8), 'iss': 'tool-rhythm'},
                      SECRET, algorithm='HS256')


def current(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials:
        try:
            return jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'], issuer='tool-rhythm',
                              options={'require': ['sub', 'role', 'exp', 'iss']})
        except jwt.InvalidTokenError:
            pass
    raise HTTPException(401, '请先登录或重新登录', headers={'WWW-Authenticate': 'Bearer'})


def only(role: Role):
    def check(viewer=Depends(current)):
        if viewer['role'] != role:
            raise HTTPException(403, '当前角色无权执行这项操作')
        return viewer
    return check
