"""GitHub App client: everything our bot does on GitHub.

How GitHub App auth works, in two steps:
1. We sign a short-lived JWT with the App's private key. That proves we are the App.
2. We swap the JWT for an installation token, which can act on the repos the App is
   installed on. It lasts an hour, so we cache it and refresh it a minute early.

Plain httpx + PyJWT instead of PyGithub: it's a few small functions we can read end to
end, and every call has an explicit timeout (a demo-stability rule).
"""

import hashlib
import hmac
import threading
import time

import httpx
import jwt

from app.config import settings

API = "https://api.github.com"
TIMEOUT_SECONDS = 10.0
API_VERSION = "2022-11-28"


class GitHubError(Exception):
    """A GitHub call failed or the App isn't configured."""


# --- Webhook signatures --------------------------------------------------------


def signature_is_valid(body: bytes, signature_header: str | None) -> bool:
    """Check X-Hub-Signature-256 against the raw request body.

    GitHub signs the exact bytes it sent, so this must run on the raw body, before any
    JSON parsing. compare_digest takes the same time whether the first byte or the last
    one differs, so an attacker can't guess the signature one byte at a time.
    """
    secret = settings.github_webhook_secret
    if secret is None or not signature_header or not signature_header.startswith("sha256="):
        return False  # no secret configured means we reject everything, never accept everything
    expected = hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


# --- Auth ----------------------------------------------------------------------

_token_lock = threading.Lock()
_token: str | None = None
_token_expires_at = 0.0


def _app_jwt() -> str:
    if not (settings.github_app_id and settings.github_private_key_path):
        raise GitHubError("GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH must be set")
    try:
        private_key = settings.github_private_key_path.read_text()
    except OSError as e:
        raise GitHubError("Couldn't read the GitHub App private key file") from e
    now = int(time.time())
    # iat is backdated a minute in case our clock is ahead of GitHub's. GitHub allows 10 minutes max.
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": settings.github_app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")


def _installation_token() -> str:
    global _token, _token_expires_at
    with _token_lock:  # background tasks run in a thread pool, so two could refresh at once
        if _token and time.time() < _token_expires_at - 60:
            return _token
        if not settings.github_installation_id:
            raise GitHubError("GITHUB_INSTALLATION_ID must be set")
        data = _request(
            "POST",
            f"/app/installations/{settings.github_installation_id}/access_tokens",
            auth=f"Bearer {_app_jwt()}",
        ).json()
        _token = data["token"]
        # Tokens last an hour. Count from now rather than parsing expires_at: close enough,
        # and we already refresh a minute early.
        _token_expires_at = time.time() + 55 * 60
        return _token


def _request(method: str, path: str, auth: str | None = None, accept: str = "application/vnd.github+json", **kwargs) -> httpx.Response:
    headers = {
        "Accept": accept,
        "Authorization": auth or f"Bearer {_installation_token()}",
        "X-GitHub-Api-Version": API_VERSION,
    }
    try:
        response = httpx.request(method, API + path, headers=headers, timeout=TIMEOUT_SECONDS, **kwargs)
    except httpx.HTTPError as e:
        raise GitHubError(f"Couldn't reach GitHub: {type(e).__name__}") from e
    if response.is_error:
        # Only the status and path go in the error, never the headers (they hold the token).
        raise GitHubError(f"GitHub {method} {path} returned {response.status_code}")
    return response


# --- What the bot does ---------------------------------------------------------


def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """The PR's unified diff, as GitHub shows it on the Files tab."""
    return _request("GET", f"/repos/{repo_full_name}/pulls/{pr_number}", accept="application/vnd.github.diff").text


def post_comment(repo_full_name: str, pr_number: int, body: str) -> int:
    """Post a comment on the PR's conversation tab as the bot. Returns the comment id."""
    # PRs are issues on GitHub's side, so PR conversation comments go through the issues API.
    response = _request("POST", f"/repos/{repo_full_name}/issues/{pr_number}/comments", json={"body": body})
    return response.json()["id"]
