import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config.database import database
from src.config.queue import redis
from src.middlewares.http import response_headers
from src.routes.api import router

app = FastAPI(title='溪巷工坊·共享工具站节律分型')
app.middleware('http')(response_headers)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = ['.'.join(str(key) for key in error['loc'][1:]) for error in exc.errors()]
    return JSONResponse(status_code=422, content={'detail': '请核对输入字段及其范围', 'fields': fields})


@app.get('/health')
def health():
    try:
        with database() as cursor:
            cursor.execute('SELECT 1 FROM stations LIMIT 1')
        redis.ping()
    except Exception:
        logging.exception('Dependency readiness check failed')
        return JSONResponse(status_code=503, content={'status': 'unavailable'})
    return {'status': 'ok', 'database': 'mysql', 'queue': 'redis'}
