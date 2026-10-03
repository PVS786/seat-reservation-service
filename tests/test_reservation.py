import pytest
import asyncio
import jwt
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.database import engine

def create_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, "test_secret", algorithm="HS256")

import pytest_asyncio

@pytest_asyncio.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest_asyncio.fixture(autouse=True)
async def clear_database():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE service.reservation_seats, service.reservations, service.seats, service.user_show_booking_state, service.shows CASCADE"))
    yield

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def create_show(client: AsyncClient, name="test-show", seats=None, price=1000):
    if seats is None:
        seats = ["A1", "A2", "A3", "A4", "A5"]
    response = await client.post("/shows", json={
        "name": name,
        "seats": seats,
        "price_paise": price
    })
    return response.json()

@pytest.mark.asyncio
async def test_successful_reservation(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    token = create_token("user1")
    
    response = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1", "A2"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount_paise"] == 2000
    assert data["status"] == "confirmed"
    assert "A1" in data["seats"]
    assert "A2" in data["seats"]

@pytest.mark.asyncio
async def test_same_seat_requested_twice_sequentially(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    
    token1 = create_token("user1")
    res1 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": "key1"}
    )
    assert res1.status_code == 201

    token2 = create_token("user2")
    res2 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": "key2"}
    )
    assert res2.status_code == 409

@pytest.mark.asyncio
async def test_concurrent_requests_same_seat(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    
    async def make_request(user_idx):
        token = create_token(f"user{user_idx}")
        return await client.post(
            f"/shows/{show_id}/reserve",
            json={"seats": ["A1"]},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"key{user_idx}"}
        )
    
    results = await asyncio.gather(*[make_request(i) for i in range(10)])
    
    successes = [r for r in results if r.status_code == 201]
    conflicts = [r for r in results if r.status_code == 409]
    
    assert len(successes) == 1
    assert len(conflicts) == 9

@pytest.mark.asyncio
async def test_concurrent_requests_multiple_seats(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    
    async def make_request(user_idx, seats):
        token = create_token(f"user{user_idx}")
        return await client.post(
            f"/shows/{show_id}/reserve",
            json={"seats": seats},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"key{user_idx}"}
        )
    
    # user0 wants A1, A2
    # user1 wants A2, A3
    # user2 wants A3, A4
    results = await asyncio.gather(
        make_request(0, ["A1", "A2"]),
        make_request(1, ["A2", "A3"]),
        make_request(2, ["A3", "A4"])
    )
    
    successes = [r for r in results if r.status_code == 201]
    assert len(successes) >= 1  # At least one should succeed, some might fail due to conflicts

@pytest.mark.asyncio
async def test_per_user_limit_concurrent(client: AsyncClient):
    show = await create_show(client, seats=["S1", "S2", "S3", "S4", "S5", "S6"])
    show_id = show["id"]
    token = create_token("user1")
    
    async def make_request(req_idx, seat):
        return await client.post(
            f"/shows/{show_id}/reserve",
            json={"seats": [seat]},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"key{req_idx}"}
        )
    
    # Fire 6 concurrent requests for different seats. Limit is 4.
    results = await asyncio.gather(
        make_request(1, "S1"),
        make_request(2, "S2"),
        make_request(3, "S3"),
        make_request(4, "S4"),
        make_request(5, "S5"),
        make_request(6, "S6"),
    )
    
    successes = [r for r in results if r.status_code == 201]
    conflicts = [r for r in results if r.status_code == 409]
    
    assert len(successes) == 4
    assert len(conflicts) == 2

@pytest.mark.asyncio
async def test_idempotency_same_request(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    token = create_token("user1")
    
    res1 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res1.status_code == 201
    
    res2 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res2.status_code == 201
    assert res1.json()["reservation_id"] == res2.json()["reservation_id"]

@pytest.mark.asyncio
async def test_idempotency_different_request(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    token = create_token("user1")
    
    res1 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res1.status_code == 201
    
    res2 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A2"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res2.status_code == 409

@pytest.mark.asyncio
async def test_rollback_does_not_leave_partial_state(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]
    token = create_token("user1")
    
    # Try to book one valid and one invalid seat
    res = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1", "INVALID_SEAT"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res.status_code == 409
    
    # Try to book A1 again, it should be available
    res2 = await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key2"}
    )
    assert res2.status_code == 201
