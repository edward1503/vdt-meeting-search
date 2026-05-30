"""Unit tests cho RRF fusion + meeting-level aggregation (không cần ES)."""

from src.search.hybrid import _rrf, _aggregate_meetings


def _hit(chunk_id, meeting_id, **extra):
    base = {"chunk_id": chunk_id, "meeting_id": meeting_id, "source": "qmsum",
            "title": "M", "text": "t", "speakers": [], "highlight": []}
    base.update(extra)
    return base


def test_rrf_rewards_items_ranked_high_in_both_lists():
    a = _hit("c1", "m1")
    b = _hit("c2", "m2")
    # c1 đứng đầu cả hai list -> phải xếp trên c2.
    fused = _rrf([[a, b], [a, b]])
    assert fused[0]["chunk_id"] == "c1"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_aggregate_groups_by_meeting_and_uses_max_score():
    hits = [
        _hit("c1", "m1", rrf_score=0.9, speakers=["A"]),
        _hit("c2", "m1", rrf_score=0.5, speakers=["B"]),
        _hit("c3", "m2", rrf_score=0.4, speakers=["C"]),
    ]
    meetings = _aggregate_meetings(hits, top_k=10)
    assert meetings[0]["meeting_id"] == "m1"
    # score = max(0.9, 0.5) + small boost cho evidence thêm
    assert meetings[0]["score"] >= 0.9
    assert set(meetings[0]["participants"]) == {"A", "B"}


def test_aggregate_caps_evidence_at_three():
    hits = [_hit(f"c{i}", "m1", rrf_score=1.0 / (i + 1)) for i in range(5)]
    meetings = _aggregate_meetings(hits, top_k=10)
    assert len(meetings[0]["evidence"]) == 3
