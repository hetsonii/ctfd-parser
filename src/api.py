"""
Low-level CTFd REST API client.
All methods return plain dicts/lists; no business logic here.
"""
from __future__ import annotations

import sys
import time
from typing import Any

import requests


_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF  = 2.0   # seconds; doubles on each retry


class CTFdAPIError(RuntimeError):
    pass


class CTFdClient:
    def __init__(self, base_url: str, session: requests.Session) -> None:
        self.base = base_url.rstrip("/")
        self._s   = session

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get(self, path: str, **kwargs) -> dict:
        url     = self.base + path
        backoff = _RETRY_BACKOFF
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                r = self._s.get(url, **kwargs)
            except requests.RequestException as exc:
                if attempt == _RETRY_ATTEMPTS:
                    raise CTFdAPIError(f"Network error on {path}: {exc}") from exc
                time.sleep(backoff)
                backoff *= 2
                continue

            if r.status_code == 429:
                retry_after = float(r.headers.get("Retry-After", backoff))
                time.sleep(retry_after)
                continue

            if r.status_code != 200:
                raise CTFdAPIError(f"HTTP {r.status_code} on {path}")

            try:
                data = r.json()
            except ValueError as exc:
                raise CTFdAPIError(f"Invalid JSON from {path}") from exc

            if not data.get("success"):
                raise CTFdAPIError(f"API success=false on {path}: {data}")

            return data

        raise CTFdAPIError(f"Exhausted retries for {path}")

    def _paginate(self, path: str) -> list[dict]:
        results   = []
        next_page: int | None = 1
        while next_page is not None:
            data      = self._get(f"{path}?page={next_page}")
            results  += data["data"]
            next_page = (data.get("meta") or {}).get("pagination", {}).get("next")
        return results

    # ------------------------------------------------------------------ #
    #  Public API surface                                                  #
    # ------------------------------------------------------------------ #

    def me(self) -> dict:
        return self._get("/api/v1/users/me")["data"]

    def challenges(self) -> list[dict]:
        return self._get("/api/v1/challenges")["data"]

    def challenge(self, chall_id: int) -> dict:
        return self._get(f"/api/v1/challenges/{chall_id}")["data"]

    def user_solves(self, user_id: int) -> set[int]:
        data = self._get(f"/api/v1/users/{user_id}/solves")["data"]
        return {s["challenge_id"] for s in data}

    def team_solves(self, team_id: int) -> set[int]:
        data = self._get(f"/api/v1/teams/{team_id}/solves")["data"]
        return {s["challenge_id"] for s in data}

    def my_solves(self) -> set[int]:
        me = self.me()
        if me.get("team_id"):
            return self.team_solves(me["team_id"])
        return self.user_solves(me["id"])

    def scoreboard(self) -> list[dict]:
        return self._get("/api/v1/scoreboard")["data"]

    def scoreboard_top(self, n: int = 1_000_000) -> dict:
        return self._get(f"/api/v1/scoreboard/top/{n}")["data"]

    def teams(self) -> list[dict]:
        return self._paginate("/api/v1/teams")

    def users(self) -> list[dict]:
        return self._paginate("/api/v1/users")

    def download_file(
        self,
        file_url: str,
        dest_path: str,
        max_bytes: int,
        chunk_size: int = 16 * 1024,
    ) -> bool:
        url = self.base + file_url
        try:
            head = self._s.head(url, allow_redirects=True, timeout=15)
            content_len = int(head.headers.get("Content-Length", 0))
            if content_len and content_len > max_bytes:
                return False
        except requests.RequestException:
            pass

        r = self._s.get(url, stream=True, timeout=60)
        if r.status_code != 200:
            raise CTFdAPIError(f"HTTP {r.status_code} downloading {file_url}")

        written = 0
        with open(dest_path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=chunk_size):
                written += len(chunk)
                if written > max_bytes:
                    fh.close()
                    import os; os.remove(dest_path)
                    return False
                fh.write(chunk)
        return True