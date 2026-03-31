import requests
import json

BASE_URL = "http://127.0.0.1:8000"


def test_healthz():
    """测试 /healthz 接口"""
    url = f"{BASE_URL}/healthz"
    
    try:
        resp = requests.get(url, timeout=10)
        print(f"=== /healthz Test ===")
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"Status: {data.get('status')}")
            print(f"Weight Root: {data.get('weight_root')}")
            print(f"Available Weights: {data.get('available_weights')}")
            print(f"Cached Models: {data.get('cached_models')}")
            print("✓ /healthz test passed")
            return True
        else:
            print(f"✗ /healthz test failed with status code {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ /healthz test failed with exception: {e}")
        return False


def test_ready():
    """测试 /ready 接口"""
    url = f"{BASE_URL}/ready"
    
    try:
        resp = requests.get(url, timeout=10)
        print(f"\n=== /ready Test ===")
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"Status: {data.get('status')}")
            print(f"Available Weights: {data.get('available_weights')}")
            print(f"Cached Models: {data.get('cached_models')}")
            print("✓ /ready test passed - Service is ready")
            return True
        elif resp.status_code == 503:
            print(f"⚠ /ready returned 503 - Service not ready")
            print(f"Response: {resp.text}")
            print("Note: This is expected if no models are loaded yet")
            return False
        else:
            print(f"✗ /ready test failed with status code {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ /ready test failed with exception: {e}")
        return False


def test_all_probes():
    """运行所有探针测试"""
    print("=" * 50)
    print("Starting Health and Readiness Probe Tests")
    print("=" * 50)
    
    healthz_passed = test_healthz()
    ready_passed = test_ready()
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("=" * 50)
    print(f"/healthz: {'✓ PASSED' if healthz_passed else '✗ FAILED'}")
    print(f"/ready:   {'✓ PASSED' if ready_passed else '⚠ NOT READY' if not healthz_passed else '✗ FAILED'}")
    print("=" * 50)
    
    return healthz_passed and ready_passed


if __name__ == "__main__":
    test_all_probes()
