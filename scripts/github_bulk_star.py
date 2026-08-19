#!/usr/bin/env python3
"""Preview or apply a bounded batch of GitHub Stars."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable


API_ROOT = "https://api.github.com"
MAX_LINKS = 6
FIRST_PAGE_SIZE = 30
USER_AGENT = "github-bulk-star-skill/1.0"


class BulkStarError(RuntimeError):
    pass


@dataclass(frozen=True)
class InputLink:
    kind: str
    owner: str
    repo: str | None = None


@dataclass(frozen=True)
class Repository:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_link(raw: str) -> InputLink:
    value = raw.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise BulkStarError(f"Unsupported GitHub link: {raw}")

    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    query = urllib.parse.parse_qs(parsed.query)
    if len(parts) == 1 and query.get("tab") == ["repositories"]:
        return InputLink("profile", parts[0])
    if len(parts) == 2 and not parsed.query:
        repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        if not repo:
            raise BulkStarError(f"Missing repository name: {raw}")
        return InputLink("repository", parts[0], repo)
    raise BulkStarError(
        "Expected https://github.com/owner/repo or "
        f"https://github.com/owner?tab=repositories: {raw}"
    )


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def request(self, method: str, path: str) -> tuple[int, bytes]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            API_ROOT + path,
            method=method,
            headers=headers,
            data=b"" if method == "PUT" else None,
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as error:
                return error.code, error.read()
            except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as error:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                reason = getattr(error, "reason", error)
                raise BulkStarError(f"GitHub request failed after one retry: {reason}") from error
        raise AssertionError("unreachable")

    def list_first_page(self, owner: str) -> list[Repository]:
        quoted_owner = urllib.parse.quote(owner, safe="")
        query = urllib.parse.urlencode(
            {"per_page": FIRST_PAGE_SIZE, "page": 1, "sort": "updated", "direction": "desc"}
        )
        status, body = self.request("GET", f"/users/{quoted_owner}/repos?{query}")
        if status != 200:
            raise BulkStarError(f"Could not list repositories for {owner} (HTTP {status})")
        payload = json.loads(body)
        return [
            Repository(item["owner"]["login"], item["name"])
            for item in payload
            if not item.get("private", False)
        ]

    def is_starred(self, repository: Repository) -> bool:
        status, _ = self.request("GET", f"/user/starred/{repository.full_name}")
        if status == 204:
            return True
        if status == 404:
            return False
        raise BulkStarError(f"Could not check {repository.full_name} (HTTP {status})")

    def star(self, repository: Repository) -> None:
        status, _ = self.request("PUT", f"/user/starred/{repository.full_name}")
        if status != 204:
            raise BulkStarError(f"Could not Star {repository.full_name} (HTTP {status})")


def resolve_repositories(raw_links: Iterable[str], client: GitHubClient) -> tuple[list[Repository], int]:
    links = list(raw_links)
    if not links:
        raise BulkStarError("Provide at least one GitHub link")
    if len(links) > MAX_LINKS:
        raise BulkStarError(f"At most {MAX_LINKS} GitHub links are allowed per run")

    resolved: list[Repository] = []
    seen: set[str] = set()
    duplicates = 0
    for raw in links:
        parsed = parse_link(raw)
        candidates = (
            client.list_first_page(parsed.owner)
            if parsed.kind == "profile"
            else [Repository(parsed.owner, parsed.repo or "")]
        )
        for repository in candidates:
            key = repository.full_name.casefold()
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            resolved.append(repository)
    return resolved, duplicates


def discover_token() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    if shutil.which("gh"):
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise BulkStarError(
        "Execution needs GH_TOKEN, GITHUB_TOKEN, or an authenticated GitHub CLI session"
    )


def apply_stars(repositories: Iterable[Repository], client: GitHubClient) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"starred": [], "skipped": [], "failed": []}
    for repository in repositories:
        try:
            if client.is_starred(repository):
                result["skipped"].append(repository.full_name)
                continue
            client.star(repository)
            result["starred"].append(repository.full_name)
            time.sleep(0.25)
        except BulkStarError as error:
            result["failed"].append(str(error))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("links", nargs="+", help="One to six GitHub repository or repositories-page links")
    parser.add_argument("--execute", action="store_true", help="Apply the previewed Stars")
    parser.add_argument("--confirm", help="Required value STAR when --execute is used")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.execute and args.confirm != "STAR":
        print("ERROR: --execute requires --confirm STAR", file=sys.stderr)
        return 2
    try:
        preview_client = GitHubClient()
        repositories, duplicates = resolve_repositories(args.links, preview_client)
        print(f"Resolved {len(repositories)} repositories ({duplicates} duplicates removed):")
        for repository in repositories:
            print(f"- {repository.full_name}")
        if not args.execute:
            print("Preview only. No GitHub Stars were changed.")
            return 0

        result = apply_stars(repositories, GitHubClient(discover_token()))
        print(
            f"Result: {len(result['starred'])} Starred, "
            f"{len(result['skipped'])} already Starred, {len(result['failed'])} failed."
        )
        for failure in result["failed"]:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1 if result["failed"] else 0
    except (BulkStarError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
