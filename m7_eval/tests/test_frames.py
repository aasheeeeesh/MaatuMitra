"""Seen-frame vs unseen-frame marker (D-90): computed from TEMPLATE text only."""

from m7_eval import frames

DEV_T = {"role": "doctor", "text": "[[m1|{D1.name} {D1.dose} ದಿನಕ್ಕೆ {D1.freq}]], ಊಟದ ನಂತರ."}
TEST_SAME = {"role": "doctor", "text": "[[m2|{D2.name} {D2.dose} ದಿನಕ್ಕೆ {D2.freq}]], ಊಟದ ನಂತರ."}
TEST_NEW = {"role": "nurse", "text": "[[s1|{S1.kn}]] ಎಷ್ಟು ದಿನದಿಂದ?"}
SLOT_ONLY = {"role": "caregiver", "text": "{X1}"}


def test_frame_masks_slots_and_span_markers():
    assert frames.frame(DEV_T["text"]) == frames.frame(TEST_SAME["text"])
    assert "{" not in frames.frame(DEV_T["text"])
    assert "[[" not in frames.frame(DEV_T["text"])


def test_clause_frames_split_on_punctuation():
    assert len(frames.clause_frames(DEV_T["text"])) == 2


def test_overlap_marker():
    families = {
        "x__f1": ("dev", [{"id": "x1", "turns": [DEV_T, SLOT_ONLY]}]),
        "x__f2": ("test", [{"id": "x2", "turns": [TEST_SAME, TEST_NEW, SLOT_ONLY]}]),
    }
    rows = frames.overlap_rows(families)
    test_rows = [r for r in rows if r["split"] == "test"]
    assert [
        (r["template_id"], r["turn_index"], r["turn_frame_seen_in_dev"]) for r in test_rows
    ] == [
        ("x2", 0, True),
        ("x2", 1, False),
        ("x2", 2, True),
    ]
    assert [r["frame_status"] for r in test_rows] == ["seen", "unseen", "slot_only"]
    assert test_rows[0]["clauses_seen_in_dev"] == 2 and test_rows[1]["clauses_seen_in_dev"] == 0
    assert all("text" not in r for r in rows)  # no template text is written out


def test_template_of_conversation():
    assert frames.template_of("m1-a5-000") == "a5"
    assert frames.template_of("fx-asha-001") is None
