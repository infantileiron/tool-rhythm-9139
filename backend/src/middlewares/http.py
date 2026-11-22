from uuid import uuid4


async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Request-Id'] = uuid4().hex
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
