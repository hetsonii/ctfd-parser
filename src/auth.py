"""
Authentication strategies for CTFd.
Each strategy returns a ready-to-use requests.Session.

Supported methods:
  - Session cookie   (--session)
  - Username + Password  (--username / --password)
"""
from __future__ import annotations

import re

import requests


class AuthError(RuntimeError):
    pass


def _base(url: str) -> str:
    # Fix missing slashes: "http:host" → "http://host"
    url = re.sub(r"^(https?):(?!//)", r"\1://", url.strip())
    # No scheme → default to http for bare IPs / localhost
    if not url.startswith("http"):
        url = "http://" + url
    return url.rstrip("/")


def _get_safe(s: requests.Session, url: str, base_url: str) -> requests.Response:
    try:
        return s.get(url, timeout=10)
    except requests.exceptions.ConnectionError:
        raise AuthError(
            f"Could not reach {base_url} — is the server running and the URL correct?"
        )
    except requests.exceptions.Timeout:
        raise AuthError(f"Connection to {base_url} timed out.")


def auth_cookie(base_url: str, session_cookie: str) -> requests.Session:
    """Authenticate with a CTFd session cookie."""
    base = _base(base_url)
    s    = requests.Session()
    s.cookies.set("session", session_cookie)
    s.headers.update({"Content-Type": "application/json"})

    r = _get_safe(s, base + "/api/v1/users/me", base_url)
    if r.status_code == 401:
        raise AuthError("Session cookie rejected (HTTP 401) — it may have expired.")
    if r.status_code != 200:
        raise AuthError(f"Cookie auth failed (HTTP {r.status_code})")
    return s


def auth_password(base_url: str, username: str, password: str) -> requests.Session:
    """Authenticate with username + password (scrapes CSRF nonce)."""
    base = _base(base_url)
    s    = requests.Session()

    r = _get_safe(s, base + "/login", base_url)
    match = re.search(rb"'csrfNonce':\s*\"([a-f0-9A-F]+)\"", r.content)
    nonce = match.group(1).decode() if match else ""

    try:
        r = s.post(
            base + "/login",
            data={
                "name":     username,
                "password": password,
                "_submit":  "Submit",
                "nonce":    nonce,
            },
            allow_redirects=True,
            timeout=10,
        )
    except requests.exceptions.ConnectionError:
        raise AuthError(f"Could not reach {base_url} during login.")
    except requests.exceptions.Timeout:
        raise AuthError(f"Login request to {base_url} timed out.")

    if "Your username or password is incorrect" in r.text:
        raise AuthError("Incorrect username or password.")
    if r.status_code not in (200, 302):
        raise AuthError(f"Login request failed (HTTP {r.status_code})")
    return s