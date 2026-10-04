import argparse
import jwt
import requests
import random
import uuid
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQUESTS = 100
CONCURRENCY = 50
BURST_JWT_SECRET = os.getenv("BURST_JWT_SECRET")

if not BURST_JWT_SECRET:
    raise RuntimeError("BURST_JWT_SECRET environment variable is required for testing")

def generate_token(user_id: str, role: str = "user") -> str:
    return jwt.encode({"sub": user_id, "role": role}, BURST_JWT_SECRET, algorithm="HS256")

def create_show(name: str, seats: list) -> str:
    resp = requests.post(
        f"{BASE_URL}/shows",
        headers={"Authorization": f"Bearer {generate_token('admin', role='admin')}"},
        json={"name": name, "seats": seats, "price_paise": 1000}
    )
    resp.raise_for_status()
    return resp.json()["id"]

def get_metrics(show_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/metrics")
    resp.raise_for_status()
    m = {"confirmed": 0, "seat-taken": 0, "per-user-limit": 0, "idempotent-replay": 0, "seats_available": 0}
    for line in resp.text.splitlines():
        if line.startswith("#"): continue
        parts = line.split()
        if len(parts) < 2: continue
        val = int(float(parts[1]))
        if line.startswith("reservations_confirmed_total"): m["confirmed"] = val
        elif line.startswith('reservations_declined_total{reason="seat-taken"}'): m["seat-taken"] = val
        elif line.startswith('reservations_declined_total{reason="per-user-limit"}'): m["per-user-limit"] = val
        elif line.startswith('reservations_declined_total{reason="idempotent-replay"}'): m["idempotent-replay"] = val
        elif line.startswith(f'seats_available{{show_id="{show_id}"}}'): m["seats_available"] = val
    return m

def reserve(show_id: str, token: str, key: str, seats: list) -> dict:
    try:
        resp = requests.post(
            f"{BASE_URL}/shows/{show_id}/reserve",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
            json={"seats": seats}
        )
        return {"status": resp.status_code, "data": resp.json() if resp.status_code == 201 else None}
    except requests.RequestException:
        return {"status": "error", "data": None}

def run_concurrent(tasks: list) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        for future in as_completed([executor.submit(reserve, *t) for t in tasks]):
            results.append(future.result())
    return results

def print_result(scenario: str, status_counts: Counter, extra_metrics: dict, metrics_pass: bool, recon_pass: bool, scenario_pass: bool):
    print(f"Scenario: {scenario}")
    print(f"Requests: {REQUESTS}")
    print(f"Concurrency: {CONCURRENCY}\n")
    print(f"201: {status_counts.get(201, 0)}")
    print(f"409: {status_counts.get(409, 0)}")
    print(f"5xx: {sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)}")
    print(f"Client errors: {status_counts.get('error', 0)}\n")
    
    for k, v in extra_metrics.items():
        print(f"{k}: {v}")
        
    print(f"\nReconciliation: {'PASS' if recon_pass and metrics_pass else 'FAIL'}")
    print(f"Scenario: {'PASS' if scenario_pass and metrics_pass and recon_pass else 'FAIL'}")

def run_hot_seat():
    show_id = create_show("Hot Seat Show", ["A1"])
    tasks = [(show_id, generate_token(f"user-{i}"), str(uuid.uuid4()), ["A1"]) for i in range(REQUESTS)]
    
    m_start = get_metrics(show_id)
    results = run_concurrent(tasks)
    m_end = get_metrics(show_id)
    
    show = requests.get(f"{BASE_URL}/shows/{show_id}").json()
    st = Counter(r["status"] for r in results)
    
    recon_pass = (show["available"] + show["held"] + show["confirmed"] == show["total_seats"])
    m_pass = (
        (m_end["confirmed"] - m_start["confirmed"]) == 1 and
        (m_end["seat-taken"] - m_start["seat-taken"]) == (REQUESTS - 1) and
        m_end["seats_available"] == show["available"]
    )
    scen_pass = (
        st[201] == 1 and st[409] == (REQUESTS - 1) and
        show["total_seats"] == 1 and show["confirmed"] == 1 and show["available"] == 0
    )
    
    print_result("hot-seat", st, {
        "Confirmed": f"+{m_end['confirmed'] - m_start['confirmed']}",
        "Seat-taken": f"+{m_end['seat-taken'] - m_start['seat-taken']}",
        "Available": show["available"]
    }, m_pass, recon_pass, scen_pass)

def run_per_user_limit():
    seats = [f"S{i}" for i in range(REQUESTS)]
    show_id = create_show("Per User Limit", seats)
    token = generate_token("limit-tester")
    tasks = [(show_id, token, str(uuid.uuid4()), [seats[i]]) for i in range(REQUESTS)]
    
    m_start = get_metrics(show_id)
    results = run_concurrent(tasks)
    m_end = get_metrics(show_id)
    
    show = requests.get(f"{BASE_URL}/shows/{show_id}").json()
    st = Counter(r["status"] for r in results)
    
    recon_pass = (show["available"] + show["held"] + show["confirmed"] == show["total_seats"])
    m_pass = (
        (m_end["confirmed"] - m_start["confirmed"]) == st.get(201, 0) and
        (m_end["per-user-limit"] - m_start["per-user-limit"]) == st.get(409, 0) and
        m_end["seats_available"] == show["available"]
    )
    scen_pass = (st.get(201, 0) <= 4 and (st.get(201, 0) + st.get(409, 0) == REQUESTS))
    
    print_result("per-user-limit", st, {
        "Confirmed": f"+{m_end['confirmed'] - m_start['confirmed']}",
        "Per-user-limit": f"+{m_end['per-user-limit'] - m_start['per-user-limit']}",
        "Available": show["available"]
    }, m_pass, recon_pass, scen_pass)

def run_idempotency():
    show_id = create_show("Idempotency", ["A1"])
    token, key = generate_token("idemp-tester"), str(uuid.uuid4())
    tasks = [(show_id, token, key, ["A1"]) for _ in range(REQUESTS)]
    
    m_start = get_metrics(show_id)
    results = run_concurrent(tasks)
    m_end = get_metrics(show_id)
    
    show = requests.get(f"{BASE_URL}/shows/{show_id}").json()
    st = Counter(r["status"] for r in results)
    unique_ids = {r["data"]["reservation_id"] for r in results if r["status"] == 201 and r["data"]}
    
    recon_pass = (show["available"] + show["held"] + show["confirmed"] == show["total_seats"])
    m_pass = (
        (m_end["confirmed"] - m_start["confirmed"]) == 1 and
        (m_end["idempotent-replay"] - m_start["idempotent-replay"]) == (REQUESTS - 1) and
        m_end["seats_available"] == show["available"]
    )
    scen_pass = (st[201] == REQUESTS and len(unique_ids) == 1)
    
    print_result("idempotency", st, {
        "Unique reservation IDs": len(unique_ids),
        "Confirmed": f"+{m_end['confirmed'] - m_start['confirmed']}",
        "Idempotent replay": f"+{m_end['idempotent-replay'] - m_start['idempotent-replay']}",
        "Available": show["available"]
    }, m_pass, recon_pass, scen_pass)

def run_same_key_different_request():
    seats = [f"S{i}" for i in range(REQUESTS)]
    show_id = create_show("Same Key", seats)
    token, key = generate_token("same-key-tester"), str(uuid.uuid4())
    tasks = [(show_id, token, key, [seats[i]]) for i in range(REQUESTS)]
    
    m_start = get_metrics(show_id)
    results = run_concurrent(tasks)
    m_end = get_metrics(show_id)
    
    show = requests.get(f"{BASE_URL}/shows/{show_id}").json()
    st = Counter(r["status"] for r in results)
    
    recon_pass = (show["available"] + show["held"] + show["confirmed"] == show["total_seats"])
    m_pass = (
        (m_end["confirmed"] - m_start["confirmed"]) == 1 and
        m_end["seats_available"] == show["available"]
    )
    scen_pass = (st[201] == 1 and st.get(409, 0) == (REQUESTS - 1))
    
    print_result("same-key-different-request", st, {
        "Confirmed": f"+{m_end['confirmed'] - m_start['confirmed']}",
        "Available": show["available"]
    }, m_pass, recon_pass, scen_pass)

def run_multi_seat():
    seats = [f"M{i}" for i in range(20)]
    show_id = create_show("Multi Seat", seats)
    random.seed(42)
    tasks = [(show_id, generate_token(f"u-{i}"), str(uuid.uuid4()), random.sample(seats, 3)) for i in range(REQUESTS)]
    
    m_start = get_metrics(show_id)
    results = run_concurrent(tasks)
    m_end = get_metrics(show_id)
    
    show = requests.get(f"{BASE_URL}/shows/{show_id}").json()
    st = Counter(r["status"] for r in results)
    
    all_confirmed = []
    has_three = True
    for r in results:
        if r["status"] == 201 and r["data"]:
            if len(r["data"]["seats"]) != 3: has_three = False
            all_confirmed.extend(r["data"]["seats"])
            
    recon_pass = (show["available"] + show["held"] + show["confirmed"] == show["total_seats"])
    m_pass = (
        (m_end["confirmed"] - m_start["confirmed"]) == st.get(201, 0) and
        (m_end["seat-taken"] - m_start["seat-taken"]) == st.get(409, 0) and
        m_end["seats_available"] == show["available"]
    )
    scen_pass = (
        has_three and 
        len(all_confirmed) == len(set(all_confirmed)) and 
        len(all_confirmed) == show["confirmed"]
    )
    
    print_result("multi-seat", st, {
        "Confirmed": f"+{m_end['confirmed'] - m_start['confirmed']}",
        "Seat-taken": f"+{m_end['seat-taken'] - m_start['seat-taken']}",
        "Available": show["available"]
    }, m_pass, recon_pass, scen_pass)

def run_health():
    import time
    start = time.time()
    try:
        live = requests.get(f"{BASE_URL}/health/live")
        ready = requests.get(f"{BASE_URL}/health/ready")
    except requests.RequestException as e:
        print(f"Health check failed to connect: {e}")
        return
        
    dur = time.time() - start
    scen_pass = (
        live.status_code == 200 and live.json() == {"status": "ok"} and
        ready.status_code == 200 and ready.json() == {"status": "ready", "database": "ok"}
    )
    
    print("Scenario: health")
    print(f"Live Status: {live.status_code}")
    print(f"Ready Status: {ready.status_code}")
    print(f"Duration: {dur:.3f}s\n")
    print(f"Scenario: {'PASS' if scen_pass else 'FAIL'}")

def main():
    global REQUESTS, CONCURRENCY
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["hot-seat", "per-user-limit", "idempotency", "same-key-different-request", "multi-seat", "health"])
    parser.add_argument("--requests", type=int, default=REQUESTS)
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    args = parser.parse_args()
    
    REQUESTS, CONCURRENCY = args.requests, args.concurrency
    globals()[f"run_{args.scenario.replace('-', '_')}"]()

if __name__ == "__main__":
    main()
