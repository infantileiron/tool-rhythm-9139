import hashlib
import hmac
import secrets

ROUNDS = 260_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ROUNDS)
    return f'{salt}:{digest.hex()}'


def matches(password, stored):
    salt, _, _ = stored.partition(':')
    return hmac.compare_digest(hash_password(password, salt), stored)
