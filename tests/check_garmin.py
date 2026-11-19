
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GARMIN_PERSONAL_API_KEY")

TOKEN_URL = (
    "https://personal.connectapi.garmin.com/"
    "personalapitoken-service/personal-api/"
    "personal-api-key/token"
)


def check_garmin_connection():
    if not API_KEY:
        print("ERROR: Garmin API key not found in .env")
        return

    print("Requesting Garmin access token...")

    response = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"ApiKey {API_KEY}",
            "Accept": "*/*"
        },
        timeout=30
    )

    print("HTTP status:", response.status_code)
    response.raise_for_status()

    access_token = response.text.strip()

    if not access_token:
        print("ERROR: Garmin returned an empty token.")
        print("Content-Type:", response.headers.get("Content-Type"))
        return

    if len(access_token.split(".")) != 3:
        print("ERROR: Response does not look like a JWT.")
        print("Content-Type:", response.headers.get("Content-Type"))
        print("Response length:", len(access_token))
        return

    print("SUCCESS: Garmin access token received!")
    print("Token length:", len(access_token))


if __name__ == "__main__":
    check_garmin_connection()