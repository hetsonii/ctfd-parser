"""
Dump raw CTFd data (challenges, teams, users, scoreboard) to JSON files.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api import CTFdClient


def _write(folder: str, filename: str, data) -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def dump_all(client: "CTFdClient", output_dir: str) -> dict[str, str]:
    from src.api import CTFdAPIError

    folder  = os.path.join(output_dir, "data")
    written: dict[str, str] = {}

    written["challenges"] = _write(folder, "challenges.json", client.challenges())
    print(f"  [+] challenges  → {written['challenges']}")

    try:
        written["users"] = _write(folder, "users.json", client.users())
        print(f"  [+] users       → {written['users']}")
    except CTFdAPIError as exc:
        print(f"  [-] users: {exc}")

    try:
        teams = client.teams()
        written["teams"] = _write(folder, "teams.json", teams)
        print(f"  [+] teams       → {written['teams']}")
    except CTFdAPIError as exc:
        teams = []
        print(f"  [-] teams: {exc}")

    try:
        written["scoreboard"] = _write(folder, "scoreboard.json", client.scoreboard())
        print(f"  [+] scoreboard  → {written['scoreboard']}")
    except CTFdAPIError as exc:
        print(f"  [-] scoreboard: {exc}")

    try:
        written["scoreboard_top"] = _write(
            folder, "scoreboard_top.json", client.scoreboard_top()
        )
        print(f"  [+] scoreboard_top → {written['scoreboard_top']}")
    except CTFdAPIError as exc:
        print(f"  [-] scoreboard_top: {exc}")

    if teams:
        team_solves: dict[int, list] = {}
        for team in teams:
            tid = team["id"]
            try:
                team_solves[tid] = client._get(f"/api/v1/teams/{tid}/solves")["data"]
            except CTFdAPIError:
                team_solves[tid] = []
        written["team_solves"] = _write(folder, "team_solves.json", team_solves)
        print(f"  [+] team_solves → {written['team_solves']}")

    return written