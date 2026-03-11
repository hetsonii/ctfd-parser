"""
CLI entry-point: argument parsing + interactive menu.

Non-interactive usage
─────────────────────
  python ctfd.py --url http://127.0.0.1:8000 --session COOKIE list
  python ctfd.py --url http://127.0.0.1:8000 -u USER -p PASS  download
  python ctfd.py --url http://127.0.0.1:8000 --session COOKIE  report
  python ctfd.py --url http://127.0.0.1:8000 -u USER -p PASS  dump

Interactive usage
─────────────────
  python ctfd.py
"""
from __future__ import annotations

import argparse
import os
import sys
import requests
from getpass import getpass

from src.api  import CTFdClient, CTFdAPIError
from src.auth import auth_cookie, auth_password, AuthError
from src      import downloader, reporter, dumper


# ------------------------------------------------------------------ #
#  Banner
# ------------------------------------------------------------------ #

def _banner() -> None:
    print(r"""
       _____ _______ ______  _   _____
      / ____|__   __|  ____|| | |  __ \
     | |       | |  | |__ __| | | |__) |_ _ _ __ ___  ___ _ __
     | |       | |  |  __/ _` | |  ___/ _` | '__/ __|/ _ \ '__|
     | |____   | |  | | | (_| | | |  | (_| | |  \__ \  __/ |
      \_____|  |_|  |_|  \__,_| |_|   \__,_|_|  |___/\___|_|
""")


# ------------------------------------------------------------------ #
#  Auth
# ------------------------------------------------------------------ #

def _build_client(args: argparse.Namespace) -> CTFdClient:
    try:
        if args.session:
            session = auth_cookie(args.url, args.session)
        elif args.username and args.password:
            session = auth_password(args.url, args.username, args.password)
        else:
            print("[*] Using unauthenticated session (public CTFd)")
            session = requests.Session()
            session.headers.update({"Content-Type": "application/json"})

    except AuthError as exc:
        print(f"[-] Auth failed: {exc}", file=sys.stderr)
        sys.exit(1)

    from src.auth import _base
    return CTFdClient(_base(args.url), session)


# ------------------------------------------------------------------ #
#  Sub-command handlers
# ------------------------------------------------------------------ #

def cmd_list(client: CTFdClient, args: argparse.Namespace) -> None:
    print("[*] Fetching unsolved challenges…")
    reporter.report_once(client, threads=args.threads)


def cmd_report(client: CTFdClient, args: argparse.Namespace) -> None:
    print(f"[*] Starting auto-refresh report (interval={args.interval}s)…")
    reporter.report_loop(client, interval=args.interval, threads=args.threads)


def cmd_download(client: CTFdClient, args: argparse.Namespace) -> None:
    print(f"[*] Downloading challenges to: {args.output}")
    result = downloader.download_challenges(
        client,
        output_dir=args.output,
        only_unsolved=args.only_unsolved,
        max_mb=args.max_mb,
        threads=args.threads,
    )

    print(
        f"\n[+] Done.  total={result.total}  ok={result.ok}  "
        f"skipped={result.skipped}  too_big={result.too_big}  "
        f"errors={len(result.errors)}"
    )

    for err in result.errors:
        print(f"  [!] {err}")


def cmd_dump(client: CTFdClient, args: argparse.Namespace) -> None:
    print(f"[*] Dumping CTFd data to: {args.output}")
    dumper.dump_all(client, args.output)
    print("[+] Dump complete.")


# ------------------------------------------------------------------ #
#  Interactive auth
# ------------------------------------------------------------------ #

def _prompt_auth() -> tuple[str, str | None, str | None, str | None]:
    url = input("CTFd URL: ").strip().rstrip("/")

    if not url.startswith("http"):
        url = "http://" + url

    print("\nAuth method:")
    print("  [1] Username + Password")
    print("  [2] Session cookie")
    print("  [3] No auth (public CTFd)")

    while True:
        choice = input("Choice [1/2/3]: ").strip()
        if choice in ("1", "2", "3"):
            break

    if choice == "1":
        user = input("Username: ").strip()
        pw = getpass("Password: ")
        return url, user, pw, None

    if choice == "2":
        cookie = getpass("Session cookie: ")
        return url, None, None, cookie

    return url, None, None, None


# ------------------------------------------------------------------ #
#  Interactive menu
# ------------------------------------------------------------------ #

def _interactive_menu(client: CTFdClient, output_dir: str, auth_enabled: bool) -> None:

    default_interval = 60
    default_threads = 8

    while True:

        print("\n" + "=" * 42)

        if auth_enabled:
            print("Mode: AUTHENTICATED\n")
            print("  [1] List unsolved challenges")
            print("  [2] Auto-refresh report")
            print("  [3] Download challenges + files")
            print("  [4] Dump scoreboard / teams / users")
            print("  [5] Exit")
        else:
            print("Mode: PUBLIC (no authentication)\n")
            print("  [1] Download challenges + files")
            print("  [2] Dump scoreboard / teams / users")
            print("  [3] Exit")

        print("=" * 42)

        choice = input("Choice: ").strip()

        # ---------------- AUTHENTICATED ----------------

        if auth_enabled:

            if choice == "1":
                reporter.report_once(client, threads=default_threads)

            elif choice == "2":
                raw = input(f"Refresh interval in seconds [{default_interval}]: ").strip()
                interval = int(raw) if raw.isdigit() else default_interval
                reporter.report_loop(client, interval=interval, threads=default_threads)

            elif choice == "3":

                path = input(f"Output directory [{output_dir}]: ").strip() or output_dir
                only = input("Only unsolved? [y/N]: ").strip().lower() == "y"

                raw = input("Max file size MB [100]: ").strip()
                mb = int(raw) if raw.isdigit() else 100

                result = downloader.download_challenges(
                    client,
                    output_dir=path,
                    only_unsolved=only,
                    max_mb=mb,
                    threads=default_threads,
                )

                print(
                    f"\n[+] Done.  total={result.total}  ok={result.ok}  "
                    f"skipped={result.skipped}  too_big={result.too_big}  "
                    f"errors={len(result.errors)}"
                )

                for err in result.errors:
                    print(f"  [!] {err}")

            elif choice == "4":

                path = input(f"Output directory [{output_dir}]: ").strip() or output_dir
                dumper.dump_all(client, path)
                print("[+] Dump complete.")

            elif choice == "5":
                print("Bye!")
                break

            else:
                print("[!] Invalid choice.")

        # ---------------- PUBLIC MODE ----------------

        else:

            if choice == "1":

                path = input(f"Output directory [{output_dir}]: ").strip() or output_dir
                raw = input("Max file size MB [100]: ").strip()
                mb = int(raw) if raw.isdigit() else 100

                result = downloader.download_challenges(
                    client,
                    output_dir=path,
                    only_unsolved=False,
                    max_mb=mb,
                    threads=default_threads,
                )

                print(
                    f"\n[+] Done.  total={result.total}  ok={result.ok}  "
                    f"skipped={result.skipped}  too_big={result.too_big}  "
                    f"errors={len(result.errors)}"
                )

                for err in result.errors:
                    print(f"  [!] {err}")

            elif choice == "2":

                path = input(f"Output directory [{output_dir}]: ").strip() or output_dir
                dumper.dump_all(client, path)
                print("[+] Dump complete.")

            elif choice == "3":
                print("Bye!")
                break

            else:
                print("[!] Invalid choice.")


# ------------------------------------------------------------------ #
#  Argument parser
# ------------------------------------------------------------------ #

def build_parser() -> argparse.ArgumentParser:

    p = argparse.ArgumentParser(
        prog="ctfd",
        description="CTFd challenge manager — list, download, dump.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    auth = p.add_argument_group("authentication")
    auth.add_argument("--url", "-U", metavar="URL", help="CTFd base URL")
    auth.add_argument("--session", "-s", metavar="COOKIE", help="Session cookie")
    auth.add_argument("--username", "-u", metavar="USER", help="Username")
    auth.add_argument("--password", "-p", metavar="PASS", help="Password")

    p.add_argument(
        "--output",
        "-o",
        default=os.path.join(os.getcwd(), "ctfd_output"),
        metavar="DIR",
    )

    p.add_argument("--threads", "-T", type=int, default=8)

    sub = p.add_subparsers(dest="command", title="commands")

    sub.add_parser("list", help="Print unsolved challenges sorted by solve count")

    rep = sub.add_parser("report", help="Auto-refreshing unsolved challenge table")
    rep.add_argument("--interval", "-i", type=int, default=60)

    dl = sub.add_parser("download", help="Download challenge files to disk")
    dl.add_argument("--only-unsolved", action="store_true")
    dl.add_argument("--max-mb", type=int, default=100)

    sub.add_parser("dump", help="Dump challenges, teams, users, scoreboard to JSON")

    return p


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def main() -> int:

    parser = build_parser()
    args = parser.parse_args()

    # ---------------- INTERACTIVE ----------------

    if args.command is None and not args.url:

        _banner()

        url, user, pw, cookie = _prompt_auth()

        args.url = url
        args.session = cookie
        args.username = user
        args.password = pw

        client = _build_client(args)

        auth_enabled = bool(args.session or (args.username and args.password))

        if auth_enabled:
            print("[+] Logged in.\n")
        else:
            print("[+] Connected (public mode).\n")

        _interactive_menu(client, args.output, auth_enabled)

        return 0

    # ---------------- NON-INTERACTIVE ----------------

    if not args.url:
        parser.error("--url is required in non-interactive mode")

    if not args.command:
        parser.error("a command is required (list / report / download / dump)")

    client = _build_client(args)

    dispatch = {
        "list": cmd_list,
        "report": cmd_report,
        "download": cmd_download,
        "dump": cmd_dump,
    }

    dispatch[args.command](client, args)

    return 0