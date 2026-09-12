"""Local accounts with separate storage for each account's trained models."""
import hashlib
import hmac
import os
import sqlite3

from wildlocate.core.data.environment import get_user_data_dir


def connect():
    folder = get_user_data_dir() / 'accounts'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / 'accounts.sqlite3'
    db = sqlite3.connect(path)
    os.chmod(path, 0o600)
    db.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, digest BLOB NOT NULL)')
    return db


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)


def normalize_username(username):
    if not isinstance(username, str):
        raise ValueError('Sign in to access your trained models.')
    username = username.strip().casefold()
    if not 3 <= len(username) <= 40 or not all(c.isalnum() or c in '_.-' for c in username):
        raise ValueError('Use 3–40 letters, numbers, dots, dashes or underscores for your username.')
    return username


def account_data_dir(username):
    """Resolve an authenticated local account to a stable, filesystem-safe folder."""
    username = normalize_username(username)
    identifier = hashlib.sha256(username.encode('utf-8')).hexdigest()
    return get_user_data_dir() / 'accounts' / identifier


def authenticate(username, password, create=False):
    username = normalize_username(username)
    if len(password) > 256:
        raise ValueError('Use a password of at most 256 characters.')
    if create and len(password) < 8:
        raise ValueError('Use at least 8 characters for your password.')
    db = connect()
    try:
        if create:
            salt = os.urandom(16)
            try:
                with db:
                    db.execute('INSERT INTO users VALUES (?, ?, ?)', (username, salt, password_hash(password, salt)))
            except sqlite3.IntegrityError:
                raise ValueError('That username is already taken on this computer.') from None
        else:
            record = db.execute('SELECT salt, digest FROM users WHERE username = ?', (username,)).fetchone()
            salt, expected = record if record else (bytes(16), bytes(64))
            valid = hmac.compare_digest(password_hash(password, salt), expected)
            if not valid or record is None:
                raise ValueError('The username or password doesn’t match. Try again.')
    finally:
        db.close()
    return username
