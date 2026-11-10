"""Test-split guard: test ids are refused unless ALLOW_TEST=1. Only the id LIST is read here."""

import pytest

from m3_extract import splits


def a_test_id():
    return splits.test_ids_for_guard()[0]


def test_dev_ids_are_dev_only():
    dev = splits.dev_ids()
    assert len(dev) > 0
    assert not set(dev) & set(splits.test_ids_for_guard())


def test_guard_refuses_test_id(monkeypatch):
    monkeypatch.delenv("ALLOW_TEST", raising=False)
    with pytest.raises(PermissionError):
        splits.assert_allowed(a_test_id())
    with pytest.raises(PermissionError):
        splits.assert_allowed(a_test_id() + "__gold")  # transcript audio ids too
    with pytest.raises(PermissionError):
        splits.load_gold(a_test_id())
    with pytest.raises(PermissionError):
        splits.split_ids("test")


def test_guard_allows_with_env(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST", "1")
    splits.assert_allowed(a_test_id())  # no exception; nothing is read


def test_dev_and_fixture_ids_allowed(monkeypatch):
    monkeypatch.delenv("ALLOW_TEST", raising=False)
    splits.assert_allowed(splits.dev_ids()[0])
    splits.assert_allowed("fx-asha-001")


def test_dev_parts_are_a_partition():
    tune, hold = splits.dev_parts()
    assert set(tune) | set(hold) == set(splits.dev_ids())
    assert not set(tune) & set(hold)
    assert {i.split("-")[1] for i in hold} == set(splits.HOLDOUT_TEMPLATES)


def test_llm_subset_seeded_dev_only():
    a = splits.llm_subset()
    assert a == splits.llm_subset()
    assert len(a) == 40 and set(a) <= set(splits.dev_ids())


def test_conversation_id_of():
    assert splits.conversation_id_of("m1-a1-000__gold") == "m1-a1-000"
    assert splits.conversation_id_of("m1-a1-000") == "m1-a1-000"
