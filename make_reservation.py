import httpx
import jwt

def create_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, "test_secret", algorithm="HS256")

base_url = "http://localhost:8000"

# 1. Create a show
show_payload = {
    "name": "Test Show",
    "seats": ["A1", "A2", "A3", "A4"],
    "price_paise": 10000
}
res = httpx.post(f"{base_url}/shows", json=show_payload)
print("Create Show Response:", res.status_code, res.text)
show_id = res.json()["id"]

# 2. Make a reservation
token = create_token("user-123")
headers = {
    "Authorization": f"Bearer {token}",
    "Idempotency-Key": "key-123"
}
reserve_payload = {
    "seats": ["A1", "A2"]
}
res = httpx.post(f"{base_url}/shows/{show_id}/reserve", json=reserve_payload, headers=headers)
print("Reserve Seats Response:", res.status_code, res.text)
