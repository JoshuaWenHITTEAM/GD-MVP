import requests

BASE_URL = "http://127.0.0.1:8000"


def test_healthz():
    resp = requests.get(f"{BASE_URL}/healthz", timeout=10)
    print("healthz status_code:", resp.status_code)
    print(resp.text)


def test_ready():
    resp = requests.get(f"{BASE_URL}/ready", timeout=10)
    print("ready status_code:", resp.status_code)
    print(resp.text)


if __name__ == "__main__":
    test_healthz()
    test_ready()
