"""
Terminal reporting: pretty table of unsolved challenges + auto-refresh.
"""
from __future__ import annotations

import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api import CTFdClient


_COL     = {"rank": 4, "name": 36, "cat": 20, "pts": 6, "solves": 7}
_SEP_LEN = sum(_COL.values()) + len(_COL) * 3 + 1


def _sep() -> str:
    return "-" * _SEP_LEN


def _header() -> str:
    return (
        f"{'#':<{_COL['rank']}} | "
        f"{'Challenge':<{_COL['name']}} | "
        f"{'Category':<{_COL['cat']}} | "
        f"{'Pts':>{_COL['pts']}} | "
        f"{'Solves':>{_COL['solves']}}"
    )


def _row(rank: int, c: dict) -> str:
    return (
        f"{rank:<{_COL['rank']}} | "
        f"{str(c.get('name', '?'))[:_COL['name']]:<{_COL['name']}} | "
        f"{str(c.get('category', '?'))[:_COL['cat']]:<{_COL['cat']}} | "
        f"{str(c.get('value', '?')):>{_COL['pts']}} | "
        f"{str(c.get('solves', '?')):>{_COL['solves']}}"
    )


def print_table(details: list[dict]) -> None:
    print(_sep())
    print(_header())
    print(_sep())
    for i, c in enumerate(details, 1):
        print(_row(i, c))
    print(_sep())
    print(f"\n[+] {len(details)} unsolved challenge(s) listed.\n")


def fetch_unsolved(client: "CTFdClient", threads: int = 8) -> list[dict]:
    all_challs = client.challenges()
    solved_ids = client.my_solves()
    unsolved   = [c for c in all_challs if c["id"] not in solved_ids]

    details: list[dict] = []
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {pool.submit(client.challenge, c["id"]): c for c in unsolved}
        for f in as_completed(futures):
            try:
                details.append(f.result())
            except Exception:
                pass

    details.sort(key=lambda c: c.get("solves", 0), reverse=True)
    return details


def report_once(client: "CTFdClient", threads: int = 8) -> None:
    details = fetch_unsolved(client, threads)
    print_table(details)


def report_loop(
    client:   "CTFdClient",
    interval: int = 60,
    threads:  int = 8,
) -> None:
    stop = False

    def _handler(sig, frame):
        nonlocal stop
        stop = True

    old = signal.signal(signal.SIGINT, _handler)
    try:
        while not stop:
            print("\033[2J\033[H", end="", flush=True)
            print(f"[*] Refreshing every {interval}s — Ctrl-C to stop\n")
            report_once(client, threads)
            for _ in range(interval):
                if stop:
                    break
                time.sleep(1)
    finally:
        signal.signal(signal.SIGINT, old)

    print("\n[+] Auto-refresh stopped.")