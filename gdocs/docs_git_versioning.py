"""
Google Docs Git Versioning

Provides MCP tools to snapshot Google Docs as markdown into local git repos,
enabling proper version history with diffs for any Google Doc.

Storage: ~/.google_workspace_mcp/doc_versions/{doc_id}/
Each doc gets its own git repo with:
  - document.md   (the markdown content)
  - metadata.json  (doc ID, title, URL, snapshot timestamp)
"""

import asyncio
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auth.service_decorator import require_multiple_services
from core.server import server
from core.utils import handle_http_errors
from gdocs.docs_markdown import convert_doc_to_markdown

logger = logging.getLogger(__name__)

DOC_VERSIONS_BASE = Path.home() / ".google_workspace_mcp" / "doc_versions"
DOC_FILENAME = "document.md"
METADATA_FILENAME = "metadata.json"


# ── Git helpers ──────────────────────────────────────────────────────────────


def _extract_doc_id(document_id: str) -> str:
    """Extract doc ID from a full Google Docs URL or return as-is."""
    url_match = re.search(r"/d/([\w-]+)", document_id)
    return url_match.group(1) if url_match else document_id


def _get_repo_path(doc_id: str) -> Path:
    return DOC_VERSIONS_BASE / doc_id


def _run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args),
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )


def _ensure_git_repo(doc_id: str) -> Path:
    """Create the doc version directory and initialize git if needed."""
    repo_path = _get_repo_path(doc_id)
    repo_path.mkdir(parents=True, exist_ok=True)
    if not (repo_path / ".git").exists():
        result = _run_git(repo_path, "init")
        if result.returncode != 0:
            raise RuntimeError(f"git init failed: {result.stderr}")
        # Configure git user for this repo (commits need an identity)
        _run_git(repo_path, "config", "user.email", "mcp@google-workspace-mcp.local")
        _run_git(repo_path, "config", "user.name", "Google Workspace MCP")
    return repo_path


def _write_and_commit(
    repo_path: Path,
    markdown: str,
    metadata: dict,
    message: str,
) -> dict:
    """Write files, stage, and commit. Returns commit info or None if no changes."""
    (repo_path / DOC_FILENAME).write_text(markdown, encoding="utf-8")

    # Check if document.md actually changed before committing
    _run_git(repo_path, "add", DOC_FILENAME)
    diff_check = _run_git(repo_path, "diff", "--cached", "--quiet", "--", DOC_FILENAME)
    if diff_check.returncode == 0:
        # No document changes — reset staging and skip commit
        _run_git(repo_path, "reset", "HEAD", "--", DOC_FILENAME)
        return None

    # Document changed — also write and stage metadata
    (repo_path / METADATA_FILENAME).write_text(
        json.dumps(metadata, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    _run_git(repo_path, "add", METADATA_FILENAME)

    commit_result = _run_git(repo_path, "commit", "-m", message)
    if commit_result.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit_result.stderr}")

    # Get commit info
    log_result = _run_git(
        repo_path, "log", "-1", "--format=%H|%ai|%s"
    )
    parts = log_result.stdout.strip().split("|", 2)

    # Get diff stats
    stat_result = _run_git(repo_path, "diff", "--stat", "HEAD~1", "HEAD", "--", DOC_FILENAME)
    diff_stat = stat_result.stdout.strip() if stat_result.returncode == 0 else ""

    return {
        "hash": parts[0] if len(parts) > 0 else "unknown",
        "date": parts[1] if len(parts) > 1 else "unknown",
        "message": parts[2] if len(parts) > 2 else message,
        "diff_stat": diff_stat,
    }


# ── Tools ────────────────────────────────────────────────────────────────────


@server.tool()
@handle_http_errors("git_snapshot_doc", is_read_only=True, service_type="docs")
@require_multiple_services(
    [
        {
            "service_type": "drive",
            "scopes": "drive_read",
            "param_name": "drive_service",
        },
        {"service_type": "docs", "scopes": "docs_read", "param_name": "docs_service"},
    ]
)
async def git_snapshot_doc(
    drive_service: Any,
    docs_service: Any,
    user_google_email: str,
    document_id: str,
    message: str = "",
) -> str:
    """
    Snapshot a Google Doc as markdown into a local git repository.

    Exports the document to markdown and commits it to a per-document git repo
    at ~/.google_workspace_mcp/doc_versions/{doc_id}/. Each call creates a new
    commit if the content has changed, building a full version history with diffs.

    Args:
        user_google_email: User's Google email address
        document_id: ID of the Google Doc (or full URL)
        message: Optional commit message (auto-generated if empty)

    Returns:
        str: Commit info with hash, timestamp, and diff stats
    """
    doc_id = _extract_doc_id(document_id)
    logger.info(f"[git_snapshot_doc] Doc={doc_id}, user={user_google_email}")

    # Fetch document
    doc = await asyncio.to_thread(
        docs_service.documents().get(documentId=doc_id).execute
    )
    title = doc.get("title", "Untitled")

    # Convert to markdown
    markdown = convert_doc_to_markdown(doc)

    # Build metadata
    now = datetime.now(timezone.utc)
    metadata = {
        "document_id": doc_id,
        "title": title,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
        "snapshot_timestamp": now.isoformat(),
        "user": user_google_email,
    }

    # Commit message
    if not message:
        message = f"Snapshot: {title} ({now.strftime('%Y-%m-%d %H:%M:%S UTC')})"

    # Ensure repo and commit
    repo_path = await asyncio.to_thread(_ensure_git_repo, doc_id)
    commit_info = await asyncio.to_thread(
        _write_and_commit, repo_path, markdown, metadata, message
    )

    if commit_info is None:
        # Get last commit date
        last_log = _run_git(repo_path, "log", "-1", "--format=%ai")
        last_date = last_log.stdout.strip() if last_log.returncode == 0 else "unknown"
        return (
            f"No changes detected in '{title}' since last snapshot ({last_date}).\n"
            f"Repo: {repo_path}"
        )

    lines = [
        f"Committed snapshot of '{title}'",
        f"  Commit: {commit_info['hash'][:12]}",
        f"  Date:   {commit_info['date']}",
        f"  Message: {commit_info['message']}",
        f"  Repo:   {repo_path}",
    ]
    if commit_info["diff_stat"]:
        lines.append(f"  Changes: {commit_info['diff_stat']}")

    # Count total commits
    count_result = _run_git(repo_path, "rev-list", "--count", "HEAD")
    if count_result.returncode == 0:
        lines.append(f"  Total snapshots: {count_result.stdout.strip()}")

    return "\n".join(lines)


@server.tool()
async def git_doc_history(
    document_id: str,
    max_entries: int = 20,
) -> str:
    """
    Show the git version history for a previously snapshotted Google Doc.

    Lists all commits (snapshots) for the document, showing hash, date, and
    commit message. No Google API access needed — reads from local git repo.

    Args:
        document_id: ID of the Google Doc (or full URL)
        max_entries: Maximum number of history entries to show (default: 20)

    Returns:
        str: Formatted commit history
    """
    doc_id = _extract_doc_id(document_id)
    repo_path = _get_repo_path(doc_id)

    if not (repo_path / ".git").exists():
        return (
            f"No version history found for document {doc_id}.\n"
            f"Use git_snapshot_doc to create the first snapshot."
        )

    # Read metadata for title
    meta_path = repo_path / METADATA_FILENAME
    title = doc_id
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            title = meta.get("title", doc_id)
        except (json.JSONDecodeError, OSError):
            pass

    result = await asyncio.to_thread(
        _run_git,
        repo_path,
        "log",
        f"-n{max_entries}",
        "--format=%H|%ai|%s",
    )

    if result.returncode != 0:
        return f"Error reading git log: {result.stderr}"

    lines = [f"Version history for '{title}' ({doc_id}):", ""]
    for entry in result.stdout.strip().split("\n"):
        if not entry:
            continue
        parts = entry.split("|", 2)
        if len(parts) == 3:
            hash_short = parts[0][:12]
            date = parts[1]
            msg = parts[2]
            lines.append(f"  {hash_short}  {date}  {msg}")

    # Total count
    count_result = await asyncio.to_thread(
        _run_git, repo_path, "rev-list", "--count", "HEAD"
    )
    if count_result.returncode == 0:
        total = count_result.stdout.strip()
        shown = min(int(total), max_entries)
        lines.append(f"\nShowing {shown} of {total} snapshots.")

    lines.append(f"Repo: {repo_path}")
    return "\n".join(lines)


@server.tool()
async def git_doc_diff(
    document_id: str,
    commit_a: str = "HEAD~1",
    commit_b: str = "HEAD",
) -> str:
    """
    Show the diff between two versions of a snapshotted Google Doc.

    Compares two commits in the document's git repo and returns a unified diff
    of the markdown content. No Google API access needed — reads from local git.

    Args:
        document_id: ID of the Google Doc (or full URL)
        commit_a: Starting commit reference (default: HEAD~1, i.e. previous version)
        commit_b: Ending commit reference (default: HEAD, i.e. latest version)

    Returns:
        str: Unified diff of the document markdown between the two versions
    """
    doc_id = _extract_doc_id(document_id)
    repo_path = _get_repo_path(doc_id)

    if not (repo_path / ".git").exists():
        return (
            f"No version history found for document {doc_id}.\n"
            f"Use git_snapshot_doc to create the first snapshot."
        )

    # Check commit count
    count_result = await asyncio.to_thread(
        _run_git, repo_path, "rev-list", "--count", "HEAD"
    )
    if count_result.returncode == 0 and count_result.stdout.strip() == "1":
        if "~" in commit_a:
            return (
                "Only one snapshot exists — nothing to diff against.\n"
                "Create another snapshot with git_snapshot_doc after making changes."
            )

    result = await asyncio.to_thread(
        _run_git,
        repo_path,
        "diff",
        commit_a,
        commit_b,
        "--",
        DOC_FILENAME,
    )

    if result.returncode != 0:
        return f"Error running git diff: {result.stderr.strip()}"

    if not result.stdout.strip():
        return f"No differences between {commit_a} and {commit_b}."

    # Read metadata for title
    meta_path = repo_path / METADATA_FILENAME
    title = doc_id
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            title = meta.get("title", doc_id)
        except (json.JSONDecodeError, OSError):
            pass

    header = f"Diff for '{title}' ({commit_a} → {commit_b}):\n"
    return header + result.stdout
