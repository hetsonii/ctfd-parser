"""
Terminal reporting: pretty table of unsolved challenges + auto-refresh.

Features
--------
- Score tracker  : rank and score shown above the table every refresh
- First blood    : challenges with 0-1 solves are marked with [!!]
- Delta report   : changes since the last refresh printed below the table
"""
from __future__ import annotations

import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api import CTFdClient


# ------------------------------------------------------------------ #
#  Table layout                                                        #
# ------------------------------------------------------------------ #

_COL     = {"rank": 4, "name": 36, "cat": 20, "pts": 6, "solves": 7, "fb": 4}
_SEP_LEN = sum(_COL.values()) + len(_COL) * 3 + 1

# ANSI helpers (gracefully ignored on terminals that don't support them)
_RESET  = "\033[0m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_GREEN  = "\033[92m"
_BOLD   = "\033[1m"


def _sep() -> str:
    return "-" * _SEP_LEN


def _header() -> str:
    return (
        f"{'#':<{_COL['rank']}} | "
        f"{'Challenge':<{_COL['name']}} | "
        f"{'Category':<{_COL['cat']}} | "
        f"{'Pts':>{_COL['pts']}} | "
        f"{'Solves':>{_COL['solves']}} | "
        f"{'':>{_COL['fb']}}"
    )


def _row(rank: int, c: dict) -> str:
    solves   = c.get("solves", 0)
    fb_tag   = ""
    colour   = ""

    if solves == 0:
        fb_tag = "[!!]"          # nobody solved it yet
        colour = _BOLD + _RED
    elif solves == 1:
        fb_tag = "[FB]"          # first blood opportunity
        colour = _YELLOW

    line = (
        f"{rank:<{_COL['rank']}} | "
        f"{str(c.get('name', '?'))[:_COL['name']]:<{_COL['name']}} | "
        f"{str(c.get('category', '?'))[:_COL['cat']]:<{_COL['cat']}} | "
        f"{str(c.get('value', '?')):>{_COL['pts']}} | "
        f"{str(solves):>{_COL['solves']}} | "
        f"{fb_tag:>{_COL['fb']}}"
    )
    return f"{colour}{line}{_RESET}" if colour else line


# ------------------------------------------------------------------ #
#  Score tracker                                                       #
# ------------------------------------------------------------------ #

def _print_standing(client: "CTFdClient") -> None:
    try:
        rank, score, name = client.my_standing()
        rank_str = f"#{rank}" if rank else "unranked"
        print(f"  {_BOLD}[ {name} ]{_RESET}  score: {_GREEN}{score}{_RESET}  rank: {_BOLD}{rank_str}{_RESET}\n")
    except Exception:
        pass   # standing is non-critical; never crash the report for it


# ------------------------------------------------------------------ #
#  Data fetch                                                          #
# ------------------------------------------------------------------ #

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


# ------------------------------------------------------------------ #
#  Delta                                                               #
# ------------------------------------------------------------------ #

def _compute_delta(
    prev: list[dict],
    curr: list[dict],
) -> None:
    """Print what changed between two snapshots. Silent if nothing changed."""
    if not prev:
        return   # first run — no baseline to diff against

    prev_map = {c["id"]: c for c in prev}
    curr_map = {c["id"]: c for c in curr}

    newly_solved  = [prev_map[i] for i in prev_map if i not in curr_map]
    newly_dropped = [curr_map[i] for i in curr_map if i not in prev_map]
    solve_bumps   = [
        (curr_map[i], prev_map[i].get("solves", 0), curr_map[i].get("solves", 0))
        for i in curr_map
        if i in prev_map
        and curr_map[i].get("solves", 0) != prev_map[i].get("solves", 0)
    ]

    if not any([newly_solved, newly_dropped, solve_bumps]):
        print(f"  {_BOLD}[~]{_RESET} No changes since last refresh.\n")
        return

    print(f"  {_BOLD}── Delta ────────────────────────────────{_RESET}")

    for c in newly_solved:
        print(f"  {_GREEN}[+]{_RESET} Solved by someone: {_BOLD}{c['name']}{_RESET} ({c.get('category','?')})")

    for c in newly_dropped:
        print(f"  {_YELLOW}[*]{_RESET} New challenge appeared: {_BOLD}{c['name']}{_RESET} ({c.get('category','?')})")

    for c, old_s, new_s in solve_bumps:
        diff = new_s - old_s
        print(f"  [~] {c['name']} — solves {old_s} → {new_s} (+{diff})")

    print()


# ------------------------------------------------------------------ #
#  Public interface                                                    #
# ------------------------------------------------------------------ #

def print_table(details: list[dict]) -> None:
    print(_sep())
    print(_header())
    print(_sep())
    for i, c in enumerate(details, 1):
        print(_row(i, c))
    print(_sep())
    print(f"\n[+] {len(details)} unsolved challenge(s) listed.\n")


def report_once(client: "CTFdClient", threads: int = 8) -> None:
    _print_standing(client)
    details = fetch_unsolved(client, threads)
    print_table(details)


def report_loop(
    client:   "CTFdClient",
    interval: int = 60,
    threads:  int = 8,
) -> None:
    stop = False
    prev: list[dict] = []

    def _handler(sig, frame):
        nonlocal stop
        stop = True

    old = signal.signal(signal.SIGINT, _handler)
    try:
        while not stop:
            print("\033[2J\033[H", end="", flush=True)
            print(f"[*] Refreshing every {interval}s — Ctrl-C to stop\n")

            _print_standing(client)
            curr = fetch_unsolved(client, threads)
            print_table(curr)
            _compute_delta(prev, curr)

            prev = curr

            for _ in range(interval):
                if stop:
                    break
                time.sleep(1)
    finally:
        signal.signal(signal.SIGINT, old)

    print("\n[+] Auto-refresh stopped.")