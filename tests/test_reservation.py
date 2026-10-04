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

async def create_show(client: AsyncClient, name="test-show", seats=None, price=1000, token=None):
    if seats is None:
        seats = ["A1", "A2", "A3", "A4", "A5"]
    
    if token is None:
        token = jwt.encode({"sub": "admin1", "role": "admin"}, "test_secret", algorithm="HS256")
        
    headers = {"Authorization": f"Bearer {token}"} if token != "no_token" else {}
        
    response = await client.post("/shows", json={
        "name": name,
        "seats": seats,
        "price_paise": price
    }, headers=headers)
    
    if response.status_code == 201:
        return response.json()
    return response

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

# --- Cancellation Tests ---
@pytest.mark.asyncio
async def test_owner_can_cancel_reservation(client: AsyncClient):
    show = await create_show(client)
    token = create_token("user1")
    res = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1", "A2"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res.status_code == 201
    res_id = res.json()["reservation_id"]
    
    cancel_res = await client.post(
        f"/reservations/{res_id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

@pytest.mark.asyncio
async def test_cancelled_reservation_releases_seats(client: AsyncClient):
    show = await create_show(client)
    token1 = create_token("user1")
    res1 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": "key1"}
    )
    res_id = res1.json()["reservation_id"]
    await client.post(f"/reservations/{res_id}/cancel", headers={"Authorization": f"Bearer {token1}"})
    
    token2 = create_token("user2")
    res2 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": "key2"}
    )
    assert res2.status_code == 201

@pytest.mark.asyncio
async def test_active_seat_count_decrements_on_cancel(client: AsyncClient):
    # per_user_limit is 4 by default
    show = await create_show(client, seats=["S1", "S2", "S3", "S4", "S5"])
    token = create_token("user1")
    
    # Book 4 seats
    res1 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["S1", "S2", "S3", "S4"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    assert res1.status_code == 201
    
    # Cannot book 5th
    res2 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["S5"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key2"}
    )
    assert res2.status_code == 409
    
    # Cancel the 4 seats
    res_id = res1.json()["reservation_id"]
    await client.post(f"/reservations/{res_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    
    # Now can book 5th
    res3 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["S5"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key3"}
    )
    assert res3.status_code == 201

@pytest.mark.asyncio
async def test_non_owner_receives_403(client: AsyncClient):
    show = await create_show(client)
    token1 = create_token("user1")
    res1 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": "key1"}
    )
    res_id = res1.json()["reservation_id"]
    
    token2 = create_token("user2")
    cancel_res = await client.post(f"/reservations/{res_id}/cancel", headers={"Authorization": f"Bearer {token2}"})
    assert cancel_res.status_code == 403

@pytest.mark.asyncio
async def test_already_cancelled_receives_409(client: AsyncClient):
    show = await create_show(client)
    token = create_token("user1")
    res1 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    res_id = res1.json()["reservation_id"]
    
    cancel1 = await client.post(f"/reservations/{res_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancel1.status_code == 200
    
    cancel2 = await client.post(f"/reservations/{res_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancel2.status_code == 409

# --- GET Show Tests ---
@pytest.mark.asyncio
async def test_get_show_details_and_counts(client: AsyncClient):
    show = await create_show(client, seats=["A1", "A2", "A3"])
    show_id = show["id"]
    
    # Check initial counts
    get_res = await client.get(f"/shows/{show_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["total_seats"] == 3
    assert data["available"] == 3
    assert data["held"] == 0
    assert data["confirmed"] == 0
    
    # Book a seat
    token = create_token("user1")
    await client.post(
        f"/shows/{show_id}/reserve",
        json={"seats": ["A2"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"}
    )
    
    # Check updated counts
    get_res2 = await client.get(f"/shows/{show_id}")
    data2 = get_res2.json()
    assert data2["available"] == 2
    assert data2["held"] == 0
    assert data2["confirmed"] == 1
    assert data2["available"] + data2["held"] + data2["confirmed"] == data2["total_seats"]
    
    # Verify specific seat states
    seat_a1 = next(s for s in data2["seats"] if s["seat_number"] == "A1")
    seat_a2 = next(s for s in data2["seats"] if s["seat_number"] == "A2")
    assert seat_a1["status"] == "available"
    assert seat_a2["status"] == "confirmed"

@pytest.mark.asyncio
async def test_get_unknown_show_404(client: AsyncClient):
    get_res = await client.get(f"/shows/{uuid.uuid4()}")
    assert get_res.status_code == 404

# --- Admin Auth Tests ---
@pytest.mark.asyncio
async def test_admin_can_create_show(client: AsyncClient):
    token = jwt.encode({"sub": "admin1", "role": "admin"}, "test_secret", algorithm="HS256")
    res = await client.post("/shows", json={"name": "test", "seats": ["A1"], "price_paise": 100}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201

@pytest.mark.asyncio
async def test_non_admin_cannot_create_show(client: AsyncClient):
    token = jwt.encode({"sub": "user1", "role": "user"}, "test_secret", algorithm="HS256")
    res = await client.post("/shows", json={"name": "test", "seats": ["A1"], "price_paise": 100}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_show(client: AsyncClient):
    res = await client.post("/shows", json={"name": "test", "seats": ["A1"], "price_paise": 100})
    assert res.status_code == 401
