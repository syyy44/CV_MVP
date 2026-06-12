from __future__ import annotations

from scripts.fixture_check import main


def test_fixture_check_passes(app_env):
    assert main() == 0
