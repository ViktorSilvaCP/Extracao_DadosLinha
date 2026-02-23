import requests
import json
from datetime import datetime, timedelta

def test_api():
    url = "http://localhost:15789/api/datasul/producao"
    
    # Test 1: Today's industrial date (should be 2026-01-27 if time is < 06:00:30)
    print("--- Test 1: Industrial Today ---")
    r = requests.get(url)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Count: {data.get('count')}")
    if data.get('results'):
        print(f"First Result Date: {data['results'][0]['data_turno']}")

    # Test 2: Specific date 2026-01-27
    print("\n--- Test 2: date=2026-01-27 ---")
    r = requests.get(url, params={"date": "2026-01-27"})
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Count: {data.get('count')}")

if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        print(f"Error: {e}")
