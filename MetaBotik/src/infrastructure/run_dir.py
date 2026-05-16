"""Unified run-directory layout: `results/<suite>/<mode>/<run_id>/`.

`run_id` = ISO timestamp (UTC, second precision, no colons) + 4-hex token.
The `latest` symlink is updated atomically on every new run.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

LATEST_LINK_NAME = "latest"


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(2)}"


class RunDirManager:
    """Single source of truth for results directory paths."""

    def __init__(self, base: Path = Path("results")) -> None:
        self._base = base

    @property
    def base(self) -> Path:
        return self._base

    def root_for(self, suite: str, mode: str) -> Path:
        return self._base / suite / mode

    def new_run_dir(self, suite: str, mode: str, *, run_id: str | None = None) -> Path:
        rid = run_id or new_run_id()
        path = self.root_for(suite, mode) / rid
        path.mkdir(parents=True, exist_ok=True)
        self._update_latest_symlink(suite, mode, rid)
        return path

    def latest_link(self, suite: str, mode: str) -> Path:
        return self.root_for(suite, mode) / LATEST_LINK_NAME

    def resolve(self, suite: str, mode: str, run_id: str) -> Path:
        if run_id == LATEST_LINK_NAME:
            link = self.latest_link(suite, mode)
            if not link.exists():
                raise FileNotFoundError(f"no `latest` symlink at {link}")
            return link.resolve()
        return self.root_for(suite, mode) / run_id

    def list_runs(self, suite: str, mode: str) -> list[str]:
        root = self.root_for(suite, mode)
        if not root.exists():
            return []
        return sorted(
            p.name
            for p in root.iterdir()
            if p.is_dir() and p.name != LATEST_LINK_NAME
        )

    def _update_latest_symlink(self, suite: str, mode: str, run_id: str) -> None:
        root = self.root_for(suite, mode)
        link = root / LATEST_LINK_NAME
        tmp = root / f".{LATEST_LINK_NAME}.tmp"
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        tmp.symlink_to(run_id)
        os.replace(tmp, link)
