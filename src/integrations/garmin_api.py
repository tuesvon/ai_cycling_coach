
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GARMIN_PERSONAL_API_KEY")

BASE_URL = "https://personal.connectapi.garmin.com"

TOKEN_URL = (
    f"{BASE_URL}/personalapitoken-service/"
    "personal-api/personal-api-key/token"
)


def get_access_token():
    if not API_KEY:
        raise ValueError("Garmin API key not found in .env")

    response = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"ApiKey {API_KEY}"},
        timeout=30
    )

    response.raise_for_status()

    token = response.text.strip()

    if not token:
        raise ValueError("Garmin returned an empty token")

    return token


def get_activities(days=30):
    from datetime import date, timedelta

    token = get_access_token()

    today = date.today()
    start_date = today - timedelta(days=days)

    url = f"{BASE_URL}/activitylist-service/activities/search/activities"

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        },
        params={
            "start": 0,
            "limit": 100,
            "startDate": start_date.isoformat(),
            "endDate": today.isoformat()
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()

def get_activity_details(activity_id, token=None):
    if token is None:
        token = get_access_token()

    url = f"{BASE_URL}/activity-service/activity/{activity_id}"

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        },
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def download_activity_file(activity_id, token=None):
    if token is None:
        token = get_access_token()

    url = f"{BASE_URL}/download-service/files/activity/{activity_id}"

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "*/*"
        },
        timeout=60
    )

    response.raise_for_status()
    return response.content
