import re

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_reservation import create_show, create_token


@pytest_asyncio.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


from app.metrics import reservations_confirmed_total, reservations_declined_total


def get_metric_value(metric_name, labels=None):
    if labels is None:
        labels = {}
    if metric_name == "reservations_confirmed_total":
        return reservations_confirmed_total._value.get()
    elif metric_name == "reservations_declined_total":
        try:
            return reservations_declined_total.labels(**labels)._value.get()
        except KeyError:
            return 0.0
    return 0.0


@pytest.fixture(autouse=True)
def reset_metrics():
    # Reset counters before each test
    from app.metrics import reservations_confirmed_total, reservations_declined_total

    reservations_confirmed_total._value.set(0)
    for reason in ["seat-taken", "per-user-limit", "idempotent-replay"]:
        try:
            reservations_declined_total.labels(reason=reason)._value.set(0)
        except KeyError:
            pass


@pytest.mark.asyncio
async def test_successful_reservation_increments_confirmed_counter(client: AsyncClient):
    show = await create_show(client)
    token = create_token("user1")

    initial_confirmed = get_metric_value("reservations_confirmed_total")

    res = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key1"},
    )
    assert res.status_code == 201

    final_confirmed = get_metric_value("reservations_confirmed_total")
    assert final_confirmed == initial_confirmed + 1


@pytest.mark.asyncio
async def test_idempotent_replay_metrics(client: AsyncClient):
    show = await create_show(client)
    token = create_token("user2")

    # First request
    res1 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key2"},
    )
    assert res1.status_code == 201
    initial_confirmed = get_metric_value("reservations_confirmed_total")
    initial_idempotent = get_metric_value(
        "reservations_declined_total", {"reason": "idempotent-replay"}
    )

    # Replay
    res2 = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key2"},
    )
    assert res2.status_code == 201

    final_confirmed = get_metric_value("reservations_confirmed_total")
    final_idempotent = get_metric_value(
        "reservations_declined_total", {"reason": "idempotent-replay"}
    )

    # Assert confirmed counter NOT incremented
    assert final_confirmed == initial_confirmed
    # Assert declined counter INCREMENTED
    assert final_idempotent == initial_idempotent + 1


@pytest.mark.asyncio
async def test_seat_taken_increments_counter(client: AsyncClient):
    show = await create_show(client)
    token1 = create_token("user3")
    token2 = create_token("user4")

    await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": "key3"},
    )

    initial_seat_taken = get_metric_value(
        "reservations_declined_total", {"reason": "seat-taken"}
    )

    # Conflict request
    res = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": "key4"},
    )
    assert res.status_code == 409

    final_seat_taken = get_metric_value(
        "reservations_declined_total", {"reason": "seat-taken"}
    )
    assert final_seat_taken == initial_seat_taken + 1


@pytest.mark.asyncio
async def test_per_user_limit_increments_counter(client: AsyncClient):
    show = await create_show(client, seats=["S1", "S2", "S3", "S4", "S5"])
    token = create_token("user5")

    await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["S1", "S2", "S3", "S4"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key5"},
    )

    initial_limit = get_metric_value(
        "reservations_declined_total", {"reason": "per-user-limit"}
    )

    res = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["S5"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key6"},
    )
    assert res.status_code == 409

    final_limit = get_metric_value(
        "reservations_declined_total", {"reason": "per-user-limit"}
    )
    assert final_limit == initial_limit + 1


@pytest.mark.asyncio
async def test_rolled_back_reservation_does_not_increment_confirmed(
    client: AsyncClient,
):
    show = await create_show(client)
    token = create_token("user6")

    initial_confirmed = get_metric_value("reservations_confirmed_total")

    # Request invalid seat (triggers 409 and rollback)
    res = await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["INVALID_SEAT"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key7"},
    )
    assert res.status_code == 409

    final_confirmed = get_metric_value("reservations_confirmed_total")
    assert final_confirmed == initial_confirmed


@pytest.mark.asyncio
async def test_get_metrics_endpoint(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]

    res = await client.get("/metrics")
    assert res.status_code == 200
    text = res.text

    assert "reservations_confirmed_total" in text
    assert "reservations_declined_total" in text
    assert f'seats_available{{show_id="{show_id}"}} 5.0' in text


@pytest.mark.asyncio
async def test_seats_available_matches_show_details(client: AsyncClient):
    show = await create_show(client)
    show_id = show["id"]

    # Book 1 seat
    token = create_token("user7")
    await client.post(
        f"/shows/{show['id']}/reserve",
        json={"seats": ["A1"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key8"},
    )

    # Get show details
    show_res = await client.get(f"/shows/{show_id}")
    available_seats = show_res.json()["available"]
    assert available_seats == 4

    # Get metrics
    metrics_res = await client.get("/metrics")
    text = metrics_res.text

    # Find the gauge value for this show
    match = re.search(f'seats_available{{show_id="{show_id}"}} ([0-9.]+)', text)
    assert match is not None
    gauge_val = float(match.group(1))

    assert gauge_val == 4.0
