"""E5: run every generated case against the real DB/API; 0 unauthorized successes required.

Writes results/m5_backend/access_matrix_results.jsonl and access_matrix_summary.json.
"""

import pytest

from m5_backend.matrix.run import run_matrix

pytestmark = pytest.mark.needs_db


def test_access_matrix(env):
    s = run_matrix(env)
    print("\n" + s["line"])
    print(
        f"unexpected denials: {s['unexpected_denials']}; integrity failures: {s['integrity_failures']}"
    )
    assert s["n_cases"] >= 500
    assert s["patients_rows_after_run"] >= 8  # injection strings destroyed nothing
    msg = "\n".join(
        f"{f['outcome']} {f['case']['case_id']} {f['detail']}" for f in s["failures"][:30]
    )
    assert s["unauthorized_successes"] == 0, msg
    assert s["integrity_failures"] == 0, msg
    assert s["unexpected_denials"] == 0, msg  # availability bugs, reported separately
