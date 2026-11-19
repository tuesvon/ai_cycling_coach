import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path
from cryptography.fernet import Fernet


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "athletes.db"


def get_encryption_key():
    key = os.getenv("ATHLETE_ENCRYPTION_KEY")

    if not key:
        raise ValueError(
            "Не найден ATHLETE_ENCRYPTION_KEY в переменных окружения"
        )

    return key.encode()


def get_cipher():
    return Fernet(get_encryption_key())


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                athlete_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                encrypted_api_key BLOB NOT NULL,
                PRIMARY KEY (athlete_id, provider)
            )
        """)


def save_api_key(athlete_id, provider, api_key):
    cipher = get_cipher()
    encrypted_key = cipher.encrypt(api_key.encode())

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            INSERT INTO credentials (
                athlete_id,
                provider,
                encrypted_api_key
            )
            VALUES (?, ?, ?)
            ON CONFLICT(athlete_id, provider)
            DO UPDATE SET encrypted_api_key = excluded.encrypted_api_key
        """, (athlete_id, provider, encrypted_key))


def get_api_key(athlete_id, provider):
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        result = connection.execute("""
            SELECT encrypted_api_key
            FROM credentials
            WHERE athlete_id = ? AND provider = ?
        """, (athlete_id, provider)).fetchone()

    if result is None:
        return None

    cipher = get_cipher()

    return cipher.decrypt(result[0]).decode()


def delete_api_key(athlete_id, provider):
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            DELETE FROM credentials
            WHERE athlete_id = ? AND provider = ?
        """, (athlete_id, provider))