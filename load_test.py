#!/usr/bin/env python3
"""
Load Test for Local Directory Server
Tests concurrent request handling capability.
"""

import argparse
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl
import json


def make_request(url: str, timeout: int = 10) -> dict:
    """Make a single request and return timing info."""
    start = time.perf_counter()
    result = {
        "success": False,
        "status": None,
        "duration_ms": 0,
        "error": None,
        "items": 0
    }

    try:
        # Create SSL context that doesn't verify (for self-signed certs in testing)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout, context=ctx) as response:
            result["status"] = response.status
            if response.status == 200:
                data = json.loads(response.read().decode())
                result["items"] = data.get("total_items", 0)
                result["success"] = True
    except URLError as e:
        result["error"] = str(e.reason)
    except Exception as e:
        result["error"] = str(e)

    result["duration_ms"] = (time.perf_counter() - start) * 1000
    return result


def run_load_test(url: str, num_requests: int, concurrency: int, timeout: int) -> dict:
    """Run load test with specified parameters."""
    print(f"\n{'='*60}")
    print(f"Load Test: {url}")
    print(f"Requests: {num_requests} | Concurrency: {concurrency} | Timeout: {timeout}s")
    print(f"{'='*60}\n")

    results = []
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, url, timeout) for _ in range(num_requests)]

        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            results.append(result)

            # Progress indicator
            if completed % 10 == 0 or completed == num_requests:
                success_count = sum(1 for r in results if r["success"])
                print(f"Progress: {completed}/{num_requests} | Success: {success_count}", end="\r")

    total_time = time.perf_counter() - start_time

    # Calculate statistics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    durations = [r["duration_ms"] for r in successful]

    stats = {
        "total_requests": num_requests,
        "successful": len(successful),
        "failed": len(failed),
        "success_rate": len(successful) / num_requests * 100 if num_requests > 0 else 0,
        "total_time_sec": round(total_time, 2),
        "requests_per_sec": round(num_requests / total_time, 2) if total_time > 0 else 0,
    }

    if durations:
        stats.update({
            "avg_response_ms": round(statistics.mean(durations), 2),
            "min_response_ms": round(min(durations), 2),
            "max_response_ms": round(max(durations), 2),
            "median_response_ms": round(statistics.median(durations), 2),
            "p95_response_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2) if len(durations) > 1 else durations[0],
        })

    # Print results
    print(f"\n\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total Requests:     {stats['total_requests']}")
    print(f"Successful:         {stats['successful']}")
    print(f"Failed:             {stats['failed']}")
    print(f"Success Rate:       {stats['success_rate']:.1f}%")
    print(f"Total Time:         {stats['total_time_sec']}s")
    print(f"Requests/sec:       {stats['requests_per_sec']}")

    if durations:
        print(f"\nResponse Times:")
        print(f"  Average:          {stats['avg_response_ms']}ms")
        print(f"  Minimum:          {stats['min_response_ms']}ms")
        print(f"  Maximum:          {stats['max_response_ms']}ms")
        print(f"  Median:           {stats['median_response_ms']}ms")
        print(f"  95th Percentile:  {stats['p95_response_ms']}ms")

    if failed:
        print(f"\nErrors:")
        error_counts = {}
        for r in failed:
            err = r["error"] or "Unknown"
            error_counts[err] = error_counts.get(err, 0) + 1
        for err, count in error_counts.items():
            print(f"  {err}: {count}")

    print(f"{'='*60}\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Load test for Local Directory Server")
    parser.add_argument("url", nargs="?", default="https://localhost:8050/",
                        help="Server URL to test (default: https://localhost:8050/)")
    parser.add_argument("-n", "--requests", type=int, default=100,
                        help="Total number of requests (default: 100)")
    parser.add_argument("-c", "--concurrency", type=int, default=10,
                        help="Number of concurrent requests (default: 10)")
    parser.add_argument("-t", "--timeout", type=int, default=10,
                        help="Request timeout in seconds (default: 10)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick test: 20 requests, 5 concurrent")
    parser.add_argument("--stress", action="store_true",
                        help="Stress test: 500 requests, 50 concurrent")

    args = parser.parse_args()

    if args.quick:
        args.requests = 20
        args.concurrency = 5
    elif args.stress:
        args.requests = 500
        args.concurrency = 50

    run_load_test(args.url, args.requests, args.concurrency, args.timeout)


if __name__ == "__main__":
    main()
