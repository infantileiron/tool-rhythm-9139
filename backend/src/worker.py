import logging
from pathlib import Path
from time import sleep

from redis.exceptions import RedisError

from src.config.database import database
from src.config.queue import QUEUE_KEY, redis
from src.constants.domain import ALGORITHM
from src.models.ledger import audit
from src.models.runs import run_record
from src.services.classifier import classify
from src.utils.serialize import canonical, fingerprint

HEARTBEAT = Path('/artifacts/worker-heartbeat')


def process_one():
    with database() as cursor:
        cursor.execute("SELECT GET_LOCK('tool-rhythm:worker', 0) AS locked")
        if cursor.fetchone()['locked'] != 1:
            return False
        # The lock belongs to this connection across commits and is released at close.
        # Any running row found here was left by an interrupted worker.
        cursor.execute("SELECT id FROM runs WHERE status IN ('running','queued') ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return False
        run_id = row['id']
        run = run_record(cursor, run_id)
        cursor.execute("UPDATE runs SET status='running' WHERE id=%s", (run_id,))
        cursor.connection.commit()
        try:
            if run['snapshot']['algorithm'] != ALGORITHM or fingerprint(run['snapshot']) != run['checksum']:
                raise ValueError('Snapshot version or fingerprint mismatch')
            result = classify(run['snapshot'])
        except (KeyError, TypeError, ValueError, ArithmeticError):
            logging.exception('Classification failed for run %s', run_id)
            cursor.execute("UPDATE runs SET status='failed',failure=%s WHERE id=%s",
                           ('分型计算失败，请核对输入后创建新版本', run_id))
            audit(cursor, 'worker', 'run.failed', str(run_id), {'checksum': run['checksum']})
        else:
            cursor.execute("UPDATE runs SET status='ready',result=%s WHERE id=%s", (canonical(result), run_id))
            audit(cursor, 'worker', 'run.ready', str(run_id), result['diagnostics'])
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    HEARTBEAT.unlink(missing_ok=True)
    while True:
        try:
            processed = process_one()
            HEARTBEAT.touch()
            if not processed:
                try:
                    redis.blpop(QUEUE_KEY, timeout=2)
                except RedisError:
                    sleep(2)
        except Exception:
            logging.exception('Worker loop failed, retrying')
            sleep(2)


if __name__ == '__main__':
    main()
