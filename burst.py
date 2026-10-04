import argparse
import jwt
import requests
import time
import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

BASE_URL = "http://127.0.0.1:8001"
REQUESTS = 100
CONCURRENCY = 50
JWT_SECRET = "test_secret"

def generate_token(user_id: str, role: str = "user") -> str:
    return jwt.encode({"sub": user_id, "role": role}, JWT_SECRET, algorithm="HS256")

def create_show(name: str, seats: list, price_paise: int = 1000) -> str:
    admin_token = generate_token("admin", role="admin")
    resp = requests.post(
        f"{BASE_URL}/shows",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": name, "seats": seats, "price_paise": price_paise}
    )
    resp.raise_for_status()
    return resp.json()["id"]

def get_show(show_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/shows/{show_id}")
    resp.raise_for_status()
    return resp.json()

def get_metrics(show_id: str = None) -> dict:
    resp = requests.get(f"{BASE_URL}/metrics")
    resp.raise_for_status()
    text = resp.text
    
    metrics = {
        "confirmed": 0.0,
        "seat-taken": 0.0,
        "per-user-limit": 0.0,
        "idempotent-replay": 0.0,
        "seats_available": 0.0
    }
    
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith("reservations_confirmed_total"):
            parts = line.split()
            if len(parts) >= 2:
                metrics["confirmed"] = float(parts[1])
        elif line.startswith('reservations_declined_total{reason="seat-taken"}'):
            parts = line.split()
            if len(parts) >= 2:
                metrics["seat-taken"] = float(parts[1])
        elif line.startswith('reservations_declined_total{reason="per-user-limit"}'):
            parts = line.split()
            if len(parts) >= 2:
                metrics["per-user-limit"] = float(parts[1])
        elif line.startswith('reservations_declined_total{reason="idempotent-replay"}'):
            parts = line.split()
            if len(parts) >= 2:
                metrics["idempotent-replay"] = float(parts[1])
        elif show_id and line.startswith(f'seats_available{{show_id="{show_id}"}}'):
            parts = line.split()
            if len(parts) >= 2:
                metrics["seats_available"] = float(parts[1])
                
    return metrics

def reserve(show_id: str, token: str, idempotency_key: str, seats: list) -> dict:
    try:
        resp = requests.post(
            f"{BASE_URL}/shows/{show_id}/reserve",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key
            },
            json={"seats": seats}
        )
        return {"status_code": resp.status_code, "data": resp.json() if resp.status_code == 201 else None}
    except requests.RequestException:
        return {"status_code": "error", "data": None}

def run_concurrent_requests(tasks) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(reserve, *task) for task in tasks]
        for future in as_completed(futures):
            results.append(future.result())
    return results

def check_reconciliation(show_id: str) -> tuple[bool, dict]:
    state = get_show(show_id)
    reconciled = (state["available"] + state["held"] + state["confirmed"]) == state["total_seats"]
    return reconciled, state

def print_results(scenario: str, results: list, duration: float, state: dict, reconciled: bool, scenario_pass: bool, metrics_delta: dict, metrics_pass: bool, extra_info: str = ""):
    status_counts = Counter(r["status_code"] for r in results)
    server_errors = sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)
    client_errors = status_counts.get("error", 0)

    print(f"\n=== {scenario.upper()} ===")
    print(f"Requests: {REQUESTS}")
    print(f"Concurrency: {CONCURRENCY}\n")
    print(f"201: {status_counts[201]}")
    print(f"409: {status_counts[409]}")
    print(f"5xx: {server_errors}")
    print(f"Client errors: {client_errors}\n")
    
    if extra_info:
        print(f"{extra_info}\n")
        
    print("Final state:")
    print(f"Total: {state['total_seats']}")
    print(f"Available: {state['available']}")
    print(f"Confirmed: {state['confirmed']}")
    print(f"Held: {state['held']}\n")
    
    print("Metrics:")
    print(f"Confirmed delta: {metrics_delta['confirmed']}")
    print(f"Seat-taken delta: {metrics_delta['seat-taken']}")
    print(f"Per-user-limit delta: {metrics_delta['per-user-limit']}")
    print(f"Idempotent-replay delta: {metrics_delta['idempotent-replay']}")
    print(f"Seats available metric: {metrics_delta['seats_available']}\n")
    
    print(f"Metrics reconciliation: {'PASS' if metrics_pass else 'FAIL'}")
    print(f"Reconciliation: {'PASS' if reconciled else 'FAIL'}")
    print(f"Scenario: {'PASS' if scenario_pass and metrics_pass else 'FAIL'}")


#SCENARIOS

def run_hot_seat():
    show_id = create_show("Hot Seat Show", ["A1"])
    tasks = []
    for i in range(REQUESTS):
        token = generate_token(f"user-{i}")
        tasks.append((show_id, token, str(uuid.uuid4()), ["A1"]))
    
    baseline_metrics = get_metrics(show_id)
    
    start_time = time.time()
    results = run_concurrent_requests(tasks)
    duration = time.time() - start_time
    
    reconciled, state = check_reconciliation(show_id)
    final_metrics = get_metrics(show_id)
    
    metrics_delta = {k: final_metrics[k] - baseline_metrics[k] for k in baseline_metrics if k != "seats_available"}
    metrics_delta["seats_available"] = final_metrics["seats_available"]
    
    status_counts = Counter(r["status_code"] for r in results)
    server_errors = sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)
    
    scenario_pass = (
        status_counts[201] == 1 and
        status_counts[409] == (REQUESTS - 1) and
        server_errors == 0 and
        status_counts.get("error", 0) == 0 and
        state["total_seats"] == 1 and
        state["confirmed"] == 1 and
        state["available"] == 0 and
        reconciled
    )
    metrics_pass = (
        metrics_delta["confirmed"] == 1 and
        metrics_delta["seat-taken"] == (REQUESTS - 1) and
        metrics_delta["seats_available"] == state["available"]
    )
    print_results("HOT SEAT", results, duration, state, reconciled, scenario_pass, metrics_delta, metrics_pass)

def run_per_user_limit():
    seats = [f"S{i}" for i in range(REQUESTS)]
    show_id = create_show("Per User Limit Show", seats)
    token = generate_token("limit-tester")
    
    tasks = []
    for i in range(REQUESTS):
        tasks.append((show_id, token, str(uuid.uuid4()), [seats[i]]))
        
    baseline_metrics = get_metrics(show_id)
        
    start_time = time.time()
    results = run_concurrent_requests(tasks)
    duration = time.time() - start_time
    
    reconciled, state = check_reconciliation(show_id)
    final_metrics = get_metrics(show_id)
    
    metrics_delta = {k: final_metrics[k] - baseline_metrics[k] for k in baseline_metrics if k != "seats_available"}
    metrics_delta["seats_available"] = final_metrics["seats_available"]
    
    status_counts = Counter(r["status_code"] for r in results)
    server_errors = sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)
    
    scenario_pass = (
        status_counts[201] <= 4 and
        (status_counts[201] + status_counts[409] == REQUESTS) and
        server_errors == 0 and
        status_counts.get("error", 0) == 0 and
        reconciled
    )
    metrics_pass = (
        metrics_delta["confirmed"] == status_counts.get(201, 0) and
        metrics_delta["per-user-limit"] == status_counts.get(409, 0) and
        metrics_delta["seats_available"] == state["available"]
    )
    print_results("PER-USER LIMIT", results, duration, state, reconciled, scenario_pass, metrics_delta, metrics_pass)

def run_idempotency():
    show_id = create_show("Idempotency Show", ["A1"])
    token = generate_token("idemp-tester")
    key = str(uuid.uuid4())
    
    tasks = []
    for _ in range(REQUESTS):
        tasks.append((show_id, token, key, ["A1"]))
        
    baseline_metrics = get_metrics(show_id)
        
    start_time = time.time()
    results = run_concurrent_requests(tasks)
    duration = time.time() - start_time
    
    reconciled, state = check_reconciliation(show_id)
    final_metrics = get_metrics(show_id)
    
    metrics_delta = {k: final_metrics[k] - baseline_metrics[k] for k in baseline_metrics if k != "seats_available"}
    metrics_delta["seats_available"] = final_metrics["seats_available"]
    
    status_counts = Counter(r["status_code"] for r in results)
    server_errors = sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)
    
    unique_ids = set()
    for r in results:
        if r["status_code"] == 201 and r["data"]:
            unique_ids.add(r["data"]["reservation_id"])
            
    scenario_pass = (
        status_counts[201] == REQUESTS and
        len(unique_ids) == 1 and
        server_errors == 0 and
        reconciled
    )
    metrics_pass = (
        metrics_delta["confirmed"] == 1 and
        metrics_delta["idempotent-replay"] == (REQUESTS - 1) and
        metrics_delta["seats_available"] == state["available"]
    )
    print_results("IDEMPOTENCY REPLAY", results, duration, state, reconciled, scenario_pass, metrics_delta, metrics_pass, f"Unique reservation IDs: {len(unique_ids)}")

def run_same_key_different_request():
    seats = [f"S{i}" for i in range(REQUESTS)]
    show_id = create_show("Same Key Show", seats)
    token = generate_token("same-key-tester")
    key = str(uuid.uuid4())
    
    tasks = []
    for i in range(REQUESTS):
        tasks.append((show_id, token, key, [seats[i]]))
        
    baseline_metrics = get_metrics(show_id)
        
    start_time = time.time()
    results = run_concurrent_requests(tasks)
    duration = time.time() - start_time
    
    reconciled, state = check_reconciliation(show_id)
    final_metrics = get_metrics(show_id)
    
    metrics_delta = {k: final_metrics[k] - baseline_metrics[k] for k in baseline_metrics if k != "seats_available"}
    metrics_delta["seats_available"] = final_metrics["seats_available"]
    
    status_counts = Counter(r["status_code"] for r in results)
    server_errors = sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)
    
    scenario_pass = (
        status_counts[201] == 1 and
        status_counts[409] == (REQUESTS - 1) and
        server_errors == 0 and
        reconciled
    )
    metrics_pass = (
        metrics_delta["confirmed"] == 1 and
        metrics_delta["seats_available"] == state["available"]
    )
    print_results("SAME KEY DIFFERENT REQUEST", results, duration, state, reconciled, scenario_pass, metrics_delta, metrics_pass)

def run_multi_seat():
    seats = [f"M{i}" for i in range(20)]
    show_id = create_show("Multi Seat Show", seats)
    
    random.seed(42) # Deterministic random generation for reproducibility
    tasks = []
    for i in range(REQUESTS):
        token = generate_token(f"user-multi-{i}")
        key = str(uuid.uuid4())
        req_seats = random.sample(seats, 3)
        tasks.append((show_id, token, key, req_seats))
        
    baseline_metrics = get_metrics(show_id)
        
    start_time = time.time()
    results = run_concurrent_requests(tasks)
    duration = time.time() - start_time
    
    reconciled, state = check_reconciliation(show_id)
    final_metrics = get_metrics(show_id)
    
    metrics_delta = {k: final_metrics[k] - baseline_metrics[k] for k in baseline_metrics if k != "seats_available"}
    metrics_delta["seats_available"] = final_metrics["seats_available"]
    
    status_counts = Counter(r["status_code"] for r in results)
    server_errors = sum(v for k, v in status_counts.items() if isinstance(k, int) and k >= 500)
    
    # Verify no seat confirmed multiple times and no partial success
    all_confirmed = []
    scenario_pass = True
    for r in results:
        if r["status_code"] == 201 and r["data"]:
            res_seats = r["data"]["seats"]
            all_confirmed.extend(res_seats)
            if len(res_seats) != 3:
                scenario_pass = False
                
    duplicates = len(all_confirmed) != len(set(all_confirmed))
    confirmed_match = len(all_confirmed) == state["confirmed"]
    
    if duplicates or not confirmed_match or server_errors > 0 or not reconciled:
        scenario_pass = False
        
    metrics_pass = (
        metrics_delta["confirmed"] == status_counts.get(201, 0) and
        metrics_delta["seat-taken"] == status_counts.get(409, 0) and
        metrics_delta["seats_available"] == state["available"]
    )
        
    print_results("MULTI SEAT ALL-OR-NOTHING", results, duration, state, reconciled, scenario_pass, metrics_delta, metrics_pass)


def main():
    global REQUESTS, CONCURRENCY
    
    parser = argparse.ArgumentParser(description="Seat Reservation Burst Tester")
    parser.add_argument("--scenario", required=True, choices=[
        "hot-seat", "per-user-limit", "idempotency", 
        "same-key-different-request", "multi-seat"
    ])
    parser.add_argument("--requests", type=int, default=REQUESTS)
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    
    args = parser.parse_args()
    
    REQUESTS = args.requests
    CONCURRENCY = args.concurrency
    
    if args.scenario == "hot-seat":
        run_hot_seat()
    elif args.scenario == "per-user-limit":
        run_per_user_limit()
    elif args.scenario == "idempotency":
        run_idempotency()
    elif args.scenario == "same-key-different-request":
        run_same_key_different_request()
    elif args.scenario == "multi-seat":
        run_multi_seat()

if __name__ == "__main__":
    main()
