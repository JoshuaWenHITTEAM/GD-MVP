from __future__ import annotations

import os

import requests


BASE_URL = os.getenv("TRACK_TEST_BASE_URL", "http://127.0.0.1:8003")


def print_response(name: str, resp):
    print(f"=== {name} ===")
    print("status_code:", resp.status_code)
    print("body:", resp.text)


def test_healthz():
    resp = requests.get(f"{BASE_URL}/healthz", timeout=10)
    print_response("/healthz", resp)
    if resp.status_code == 200:
        data = resp.json()
        assert data["status"] == "ok", data
        assert "available_weights" in data, data


def test_ready():
    resp = requests.get(f"{BASE_URL}/ready", timeout=10)
    print_response("/ready", resp)
    assert resp.status_code in (200, 503), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert data["status"] == "ready", data
        assert data["cached_models"], data


def test_version():
    resp = requests.get(f"{BASE_URL}/version", timeout=10)
    print_response("/version", resp)
    resp.raise_for_status()
    data = resp.json()
    assert data["version"] == "track-siamrpnpp-http-v1", data


if __name__ == "__main__":
    test_healthz()
    test_ready()
    test_version()
