"""Every module output that crosses a boundary validates against its contract (DEV data only)."""

from __future__ import annotations

import pytest

from integration import boundary


@pytest.fixture(scope="module")
def checks():
    return boundary.run_all()


def test_all_boundaries_have_data_and_no_mismatch(checks):
    problems = [(c.name, c.n, c.errors[:3]) for c in checks if not c.ok]
    assert not problems, problems


def test_boundary_report_renders(checks):
    md = boundary.render_md(checks)
    assert "| boundary | check | schema |" in md


def test_the_boundary_checks_never_list_a_test_id(checks):
    test = boundary._split_ids("test.txt")
    for c in checks:
        for where, _ in c.errors:
            assert not any(t in where for t in test)
