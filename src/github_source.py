"""Fetches CV files from a GitHub repository path.

Usage (from pipeline.py):
    files = fetch_cvs_from_github("owner/repo", "applications/pm")
    # returns a list of local temp paths ready for parse_cv()

Requires GITHUB_TOKEN in the environment for private repos. Public repos work
without a token but are rate-limited to 60 requests/hour unauthenticated.
"""
import os
import tempfile
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"
CV_EXTENSIONS = {".pdf", ".docx", ".txt"}


def fetch_cvs_from_github(repo: str, path: str = "", ref: str = "main") -> list[str]:
    """Download all CV files under `path` in `repo` and return local file paths.

    repo  — 'owner/repo-name'
    path  — directory inside the repo (default: repo root)
    ref   — branch, tag, or commit SHA (default: 'main')
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    items = _list_tree(repo, path, ref, headers)
    cv_items = [i for i in items if Path(i["name"]).suffix.lower() in CV_EXTENSIONS]

    if not cv_items:
        print(f"[github] no CV files found in {repo}/{path} at ref={ref}")
        return []

    local_paths = []
    tmp_dir = tempfile.mkdtemp(prefix="kargo_cvs_")
    for item in cv_items:
        local_path = _download_file(item["download_url"], tmp_dir, item["name"], headers)
        if local_path:
            local_paths.append(local_path)
            print(f"[github] fetched {item['name']}")

    return local_paths


def _list_tree(repo: str, path: str, ref: str, headers: dict) -> list[dict]:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=headers, params={"ref": ref}, timeout=15)
    if resp.status_code == 404:
        raise ValueError(f"GitHub path not found: {repo}/{path} at ref={ref}")
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        # single file, not a directory
        return [data] if Path(data.get("name", "")).suffix.lower() in CV_EXTENSIONS else []
    return [item for item in data if item.get("type") == "file"]


def _download_file(url: str, dest_dir: str, filename: str, headers: dict) -> str | None:
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        dest = os.path.join(dest_dir, filename)
        with open(dest, "wb") as f:
            f.write(resp.content)
        return dest
    except Exception as exc:
        print(f"[github] could not download {filename}: {exc}")
        return None
