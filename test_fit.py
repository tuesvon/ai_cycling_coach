from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fitparse import FitFile

from src.integrations.garmin_api import (
    get_access_token,
    download_activity_file
)

activity_id = 25119885413

print("=== DOWNLOADING ACTIVITY ===")

token = get_access_token()
zip_data = download_activity_file(activity_id, token)

# Извлекаем FIT из ZIP
with ZipFile(BytesIO(zip_data)) as archive:
    fit_filename = next(
        name for name in archive.namelist()
        if name.lower().endswith(".fit")
    )

    fit_data = archive.read(fit_filename)

# Сохраняем FIT в проект
output_dir = Path("data/fit")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / f"{activity_id}.fit"
output_path.write_bytes(fit_data)

print("FIT saved:", output_path)
print("File size:", len(fit_data), "bytes")

# Читаем FIT
print("\n=== READING FIT DATA ===")

fit_file = FitFile(BytesIO(fit_data))

record_count = 0

for record in fit_file.get_messages("record"):
    record_count += 1

    if record_count <= 5:
        print(f"\nRecord #{record_count}")

        for field in record:
            print(f"{field.name}: {field.value}")

print("\n=== RESULT ===")
print("Total records:", record_count)
