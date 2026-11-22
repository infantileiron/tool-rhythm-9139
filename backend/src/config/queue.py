import os

from redis import Redis

QUEUE_KEY = 'tool-rhythm:wake'
redis = Redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
                       socket_connect_timeout=2, socket_timeout=4)
