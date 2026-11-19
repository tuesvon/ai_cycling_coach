from src.athletes.athlete_manager import get_all_athletes

athletes = get_all_athletes()

print("=== REGISTERED ATHLETES ===")

for athlete in athletes:
    print(athlete)