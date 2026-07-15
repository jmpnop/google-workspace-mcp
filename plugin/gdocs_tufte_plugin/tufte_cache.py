"""
Tufte Publishing Cache

Persists doc-ID and image-hash mappings so re-publishing the same document
updates in place and identical images are not re-uploaded to Drive.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".google_workspace_mcp" / "cache" / "tufte"


class TuftePubCache:
    """File-backed cache for Tufte publishing operations."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self._dir = cache_dir or _DEFAULT_CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

        self._doc_path = self._dir / "doc_index.json"
        self._img_path = self._dir / "image_cache.json"

        self._docs: dict[str, str] = self._load(self._doc_path)
        self._images: dict[str, str] = self._load(self._img_path)

    # -- doc ID cache -------------------------------------------------------

    def get_doc_id(self, title: str) -> Optional[str]:
        """Return cached doc ID for *title*, or None."""
        return self._docs.get(title)

    def set_doc_id(self, title: str, doc_id: str) -> None:
        """Store title -> doc_id mapping and flush to disk."""
        self._docs[title] = doc_id
        self._save(self._doc_path, self._docs)
        logger.info(f"[tufte_cache] Cached doc_id for '{title}': {doc_id}")

    # -- image cache --------------------------------------------------------

    def get_image(self, content_hash: str) -> Optional[str]:
        """Return cached Drive file ID for *content_hash*, or None."""
        return self._images.get(content_hash)

    def set_image(self, content_hash: str, file_id: str) -> None:
        """Store hash -> Drive file_id and flush to disk."""
        self._images[content_hash] = file_id
        self._save(self._img_path, self._images)
        logger.debug(f"[tufte_cache] Cached image {content_hash[:12]}... -> {file_id}")

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """SHA-256 hex digest of raw bytes."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _load(path: Path) -> dict:
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"[tufte_cache] Failed to read {path}: {exc}")
        return {}

    @staticmethod
    def _save(path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)
