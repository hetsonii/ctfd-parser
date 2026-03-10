"""
Challenge downloader — builds the on-disk folder tree and
fetches all files attached to each challenge.

Output layout
─────────────
<output>/
  <Category>/
    <ChallengeName>/
      README.md
      <attached files…>
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api import CTFdClient


_DEFAULT_MAX_MB  = 100
_DEFAULT_THREADS = 8


def _sanitize(name: str) -> str:
    name = re.sub(r'[/\\:*?"<>|;]', "_", name)
    name = re.sub(r"_+", "_", name).strip("_. ")
    return name or "unknown"


def _make_dir(*parts: str) -> str:
    path = os.path.join(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def _write_readme(folder: str, detail: dict) -> None:
    lines = [
        f"# {detail['name']}\n",
        f"**Category:** {detail.get('category', '—')}  ",
        f"**Points:** {detail.get('value', '—')}  ",
        f"**Solves:** {detail.get('solves', '—')}\n",
        "---\n",
        detail.get("description") or "_No description._",
        "\n",
    ]
    conn = detail.get("connection_info") or ""
    if conn.strip():
        lines += ["\n## Connection\n", conn, "\n"]

    files = detail.get("files") or []
    if files:
        lines.append("\n## Files\n")
        for f in files:
            fname = os.path.basename(f.split("?")[0])
            lines.append(f"- [{fname}](./{fname})\n")

    with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


@dataclass
class DownloadResult:
    total:   int = 0
    skipped: int = 0
    ok:      int = 0
    too_big: int = 0
    errors:  list[str] = field(default_factory=list)


def download_challenges(
    client:        "CTFdClient",
    output_dir:    str,
    only_unsolved: bool = False,
    max_mb:        int  = _DEFAULT_MAX_MB,
    threads:       int  = _DEFAULT_THREADS,
) -> DownloadResult:
    from src.api import CTFdAPIError

    result    = DownloadResult()
    max_bytes = max_mb * 1024 * 1024

    challenges = client.challenges()
    solved_ids = client.my_solves() if only_unsolved else set()
    result.total = len(challenges)

    def _process(chall: dict) -> str | None:
        if only_unsolved and chall["id"] in solved_ids:
            return "__SKIPPED__"

        try:
            detail = client.challenge(chall["id"])
        except CTFdAPIError as exc:
            return f"[{chall.get('name', chall['id'])}] fetch detail: {exc}"

        cat    = _sanitize(detail.get("category") or "Uncategorised")
        name   = _sanitize(detail.get("name")     or str(detail["id"]))
        folder = _make_dir(output_dir, cat, name)

        _write_readme(folder, detail)

        for file_url in detail.get("files") or []:
            fname = os.path.basename(file_url.split("?")[0])
            dest  = os.path.join(folder, fname)
            if os.path.exists(dest):
                continue
            try:
                ok = client.download_file(file_url, dest, max_bytes)
                if not ok:
                    return f"[{name}/{fname}] skipped — exceeds {max_mb} MB"
            except CTFdAPIError as exc:
                return f"[{name}/{fname}] download error: {exc}"

        return None

    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {pool.submit(_process, c): c for c in challenges}
        for future in as_completed(futures):
            err = future.result()
            if err == "__SKIPPED__":
                result.skipped += 1
            elif err:
                result.errors.append(err)
                result.too_big += err.endswith("MB")
            else:
                result.ok += 1

    return result