import requests
import asyncio
import aiohttp
import subprocess
import sys

URL = "https://api.monarchmoney.com/auth/login/"

def test_requests():
    print("\n--- Testing with 'requests' (Sync) ---")
    try:
        # Just a GET to check connectivity/SSL. Login endpoint usually expects POST but GET should reply with 405 or 200
        resp = requests.get(URL)
        print(f"Status: {resp.status_code}")
        print(f"Reason: {resp.reason}")
        print("Success (Handshake worked)")
    except Exception as e:
        print(f"FAILED: {e}")

async def test_aiohttp():
    print("\n--- Testing with 'aiohttp' (Async) ---")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as resp:
                print(f"Status: {resp.status}")
                print(f"Reason: {resp.reason}")
                print("Success (Handshake worked)")
    except Exception as e:
        print(f"FAILED: {e}")

def test_curl():
    print("\n--- Testing with 'curl' (System) ---")
    try:
        cmd = ["curl", "-I", URL]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_requests()
    asyncio.run(test_aiohttp())
    test_curl()
