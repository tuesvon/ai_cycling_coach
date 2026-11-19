import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_URL = "http://localhost:1235/v1"

url = f"{BASE_URL}/models"

request = Request(
    url,
    headers={"Content-Type": "application/json"}
)

try:
    with urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("Connection successful!")
    print("\nAvailable models:")

    for model in data.get("data", []):
        print("Model ID:", model.get("id"))

except HTTPError as error:
    print("HTTP error:", error.code)
    print(error.read().decode("utf-8"))

except URLError as error:
    print("Connection failed:", error.reason)
