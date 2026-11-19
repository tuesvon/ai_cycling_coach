from src.athletes.athlete_manager import get_registered_athlete_data


def main():
    athlete_id = "i280488"

    print("=== REAL ATHLETE DATA TEST ===")
    print("Загружаем профиль из Intervals.icu...")
    print()

    try:
        data = get_registered_athlete_data(athlete_id)

    except Exception as error:
        print("Ошибка загрузки данных:")
        print(type(error).__name__, error)
        return

    print("Профиль успешно загружен!")
    print()
    print("=== ATHLETE PROFILE ===")

    fields = [
        ("ID", "id"),
        ("Name", "name"),
        ("Weight", "weight"),
        ("Height", "height"),
        ("FTP", "ftp"),
        ("Indoor FTP", "indoor_ftp"),
        ("LTHR", "lthr"),
        ("Max HR", "max_hr"),
        ("Power zones", "power_zones"),
        ("Power zone names", "power_zone_names"),
        ("HR zones", "hr_zones"),
        ("HR zone names", "hr_zone_names"),
    ]

    for label, key in fields:
        print(f"{label}: {data.get(key)}")


if __name__ == "__main__":
    main()