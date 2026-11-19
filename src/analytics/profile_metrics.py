from datetime import date

def calculate_age(date_of_birth):
    if date_of_birth is None:
        return None

    today = date.today()
    age = today.year - date_of_birth.year

    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age

def calculate_ftp_per_kg(ftp, weight):
    if weight <= 0:
        raise ValueError("Вес должен быть выше нуля")
    if ftp <= 0:
        raise ValueError("FTP должен быть выше нуля")

    return round(ftp / weight, 2)