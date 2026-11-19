from profiles import me, IanaR, MashaSt
from src.analytics.profile_metrics import calculate_age, calculate_ftp_per_kg

cyclists = [me, IanaR, MashaSt]

for cyclist in cyclists:
    print("Имя:", cyclist.name)
    print("Вес:", cyclist.weight, "кг")
    print("Рост:", cyclist.height, "см")

    age = calculate_age(cyclist.date_of_birth)
    print("Возраст:", age)

    print("FTP:", cyclist.ftp, "Вт")
    print(
        "FTP per kg:",
        calculate_ftp_per_kg(cyclist.ftp, cyclist.weight),
        "Вт/кг"
    )
    print("Максимальный пульс:", cyclist.max_heart_rate, "bpm")
    print("------")