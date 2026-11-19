import sqlite3

from src.athletes.credentials import (
    save_api_key,
    get_api_key,
    delete_api_key,
    DATABASE_PATH
)


def test_credentials():
    athlete_id = "test_athlete"
    provider = "intervals"
    test_key = "test_secret_api_key_12345"

    print("1. Сохраняем тестовый ключ...")
    save_api_key(athlete_id, provider, test_key)

    print("2. Проверяем чтение...")
    restored_key = get_api_key(athlete_id, provider)

    assert restored_key == test_key
    print("Ключ успешно восстановлен.")

    print("3. Проверяем шифрование в базе...")
    with sqlite3.connect(DATABASE_PATH) as connection:
        result = connection.execute(
            """
            SELECT encrypted_api_key
            FROM credentials
            WHERE athlete_id = ? AND provider = ?
            """,
            (athlete_id, provider)
        ).fetchone()

    assert result is not None
    assert result[0].decode() != test_key
    print("В базе хранится зашифрованное значение.")

    print("4. Проверяем удаление...")
    delete_api_key(athlete_id, provider)

    assert get_api_key(athlete_id, provider) is None
    print("Ключ успешно удалён.")

    print("\nВсе проверки пройдены!")


if __name__ == "__main__":
    test_credentials()
