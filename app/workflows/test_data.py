"""Discover and load live-test fixtures from data/test."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import MissingDocumentError, ReplayFixtureMissingError
from app.locale import zh_CN as msg
from app.workflows.parsing import ALLOWED_EXTENSIONS

JD_NAME_HINTS = ("job", "jd", "description", "职位")


@dataclass(frozen=True)
class TestDataPaths:
    jd: Path
    resumes: list[Path]


def test_data_dir() -> Path:
    return get_settings().test_data_dir


def _is_allowed(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS


def _looks_like_jd(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() == ".txt" and any(hint in name for hint in JD_NAME_HINTS)


def _discover_test_data() -> TestDataPaths:
    root = test_data_dir()
    if not root.is_dir():
        raise ReplayFixtureMissingError(msg.test_data_dir_missing(str(root)))

    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        jd_rel = payload.get("jd")
        resume_rels = payload.get("resumes") or []
        if not jd_rel or not resume_rels:
            raise ReplayFixtureMissingError(msg.test_data_manifest_invalid(str(manifest_path)))
        jd_path = root / jd_rel
        resume_paths = [root / rel for rel in resume_rels]
        missing = [str(p) for p in [jd_path, *resume_paths] if not _is_allowed(p)]
        if missing:
            raise ReplayFixtureMissingError(msg.test_data_files_missing(", ".join(missing)))
        return TestDataPaths(jd=jd_path, resumes=resume_paths)

    candidates = sorted(
        p for p in root.iterdir() if _is_allowed(p) and p.name != "manifest.json"
    )
    jd_candidates = [p for p in candidates if _looks_like_jd(p)]
    resume_candidates = [p for p in candidates if p not in jd_candidates]
    if len(jd_candidates) != 1 or not resume_candidates:
        raise ReplayFixtureMissingError(msg.test_data_auto_discover_failed(str(root)))
    return TestDataPaths(jd=jd_candidates[0], resumes=resume_candidates)


def list_test_data_files() -> TestDataPaths:
    return _discover_test_data()


def resolve_test_data_file(filename: str) -> Path:
    root = test_data_dir().resolve()
    path = (root / filename).resolve()
    if root not in path.parents and path != root:
        raise MissingDocumentError(msg.test_data_file_not_allowed(filename))
    if not _is_allowed(path):
        raise MissingDocumentError(msg.test_data_file_not_found(filename))
    discovered = _discover_test_data()
    allowed = {discovered.jd.name, *(p.name for p in discovered.resumes)}
    if path.name not in allowed:
        raise MissingDocumentError(msg.test_data_file_not_found(filename))
    return path


def read_test_data_uploads() -> tuple[tuple[str, bytes], list[tuple[str, bytes]]]:
    discovered = _discover_test_data()
    jd = (discovered.jd.name, discovered.jd.read_bytes())
    resumes = [(p.name, p.read_bytes()) for p in discovered.resumes]
    return jd, resumes
