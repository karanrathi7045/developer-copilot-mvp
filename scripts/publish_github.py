from __future__ import annotations

import base64
import fnmatch
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.github.com"
DEFAULT_REPO_NAME = "developer-copilot-mvp"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

INCLUDE_ROOTS = {
    ".env.example",
    ".gitignore",
    "DEPLOYMENT.md",
    "README.md",
    "data",
    "developer_copilot",
    "frontend",
    "lead_analytics",
    "render.yaml",
    "requirements.txt",
    "scripts",
    "tests",
}

EXCLUDE_NAMES = {
    ".DS_Store",
    ".env",
    ".git",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "storage",
}

EXCLUDE_PATTERNS = {
    "*.pyc",
    "*.pyo",
}


def main() -> None:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Missing GITHUB_TOKEN. Add it to .env or export it before running.")

    repo_name = os.getenv("GITHUB_REPO_NAME", DEFAULT_REPO_NAME)
    private = os.getenv("GITHUB_PRIVATE", "true").strip().lower() not in {"0", "false", "no"}
    owner = os.getenv("GITHUB_OWNER")
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    user = request_json(session, "GET", f"{API_BASE}/user")
    login = user["login"]
    owner = owner or login
    repo = ensure_repo(session, owner, login, repo_name, private)
    if repo.get("private") != private:
        visibility = "private" if private else "public"
        print(f"Repository exists as {'private' if repo.get('private') else 'public'}; skipping {visibility} visibility change.")

    files = list(iter_publish_files())
    for path in files:
        publish_file(session, owner, repo_name, path)

    print(f"Published {len(files)} files")
    print(f"Repository: {repo['html_url']}")


def ensure_repo(
    session: requests.Session,
    owner: str,
    login: str,
    repo_name: str,
    private: bool,
) -> dict[str, Any]:
    existing = request_json(
        session,
        "GET",
        f"{API_BASE}/repos/{owner}/{repo_name}",
        allow_404=True,
    )
    if existing:
        return existing

    payload = {"name": repo_name, "private": private, "auto_init": True}
    if owner == login:
        return request_json(session, "POST", f"{API_BASE}/user/repos", json=payload)
    return request_json(session, "POST", f"{API_BASE}/orgs/{owner}/repos", json=payload)


def publish_file(session: requests.Session, owner: str, repo_name: str, path: Path) -> None:
    repo_path = path.relative_to(ROOT).as_posix()
    encoded_path = quote(repo_path, safe="/")
    existing = request_json(
        session,
        "GET",
        f"{API_BASE}/repos/{owner}/{repo_name}/contents/{encoded_path}",
        allow_404=True,
    )
    payload: dict[str, Any] = {
        "message": f"Publish {repo_path}",
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        "branch": "main",
    }
    if existing and existing.get("sha"):
        payload["sha"] = existing["sha"]
    request_json(
        session,
        "PUT",
        f"{API_BASE}/repos/{owner}/{repo_name}/contents/{encoded_path}",
        json=payload,
    )


def iter_publish_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        parts = relative.parts
        if not parts:
            continue
        if parts[0] not in INCLUDE_ROOTS:
            continue
        if any(part in EXCLUDE_NAMES for part in parts):
            continue
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in EXCLUDE_PATTERNS):
            continue
        yield path


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    allow_404: bool = False,
    allow_statuses: set[int] | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    response = session.request(method, url, timeout=60, **kwargs)
    if allow_404 and response.status_code == 404:
        return None
    if allow_statuses and response.status_code in allow_statuses:
        return None
    if not response.ok:
        message = response.text[:500]
        raise SystemExit(f"GitHub API failed: {response.status_code} {message}")
    if response.status_code == 204:
        return {}
    return response.json()


if __name__ == "__main__":
    main()
