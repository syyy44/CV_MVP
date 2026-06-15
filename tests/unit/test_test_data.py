from __future__ import annotations

import pytest

from app.workflows.test_data import list_test_data_files, resolve_test_data_file


def test_list_test_data_from_manifest():
    paths = list_test_data_files()
    assert paths.jd.exists()
    assert paths.jd.suffix.lower() in {".txt", ".pdf", ".docx"}
    assert paths.resumes
    assert all(path.exists() for path in paths.resumes)
    assert all(path.suffix.lower() in {".txt", ".pdf", ".docx"} for path in paths.resumes)


def test_resolve_test_data_file_allows_manifest_entries():
    expected = list_test_data_files()
    path = resolve_test_data_file(expected.resumes[0].name)
    assert path.exists()


def test_resolve_test_data_file_rejects_unknown():
    with pytest.raises(Exception):  # noqa: B017
        resolve_test_data_file("../../.env")
