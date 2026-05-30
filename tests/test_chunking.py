"""Unit tests cho speaker-aware chunking (không cần ES/model)."""

from src.preprocessing.chunking import chunk_meetings


def _meeting(turns):
    return {
        "meeting_id": "qmsum_t1",
        "raw_meeting_id": "t1",
        "source": "qmsum",
        "title": "Test Meeting",
        "date": None,
        "turns": turns,
    }


def test_chunk_basic_fields_and_speaker_prefix():
    m = _meeting([
        {"speaker": "A", "text": "hello there team"},
        {"speaker": "B", "text": "yes lets begin"},
    ])
    chunks = chunk_meetings([m], target_tokens=50, max_tokens=80, overlap_tokens=10)
    assert len(chunks) == 1
    c = chunks[0]
    assert c["chunk_id"] == "qmsum_t1_00000"
    assert c["meeting_id"] == "qmsum_t1"
    assert "A: hello there team" in c["content_text"]
    assert set(c["speakers"]) == {"A", "B"}
    assert "source: qmsum" in c["metadata_text"]


def test_long_turn_is_split_with_overlap():
    long_text = " ".join(f"w{i}" for i in range(300))
    chunks = chunk_meetings([_meeting([{"speaker": "A", "text": long_text}])],
                            target_tokens=100, max_tokens=120, overlap_tokens=20)
    assert len(chunks) >= 2


def test_empty_turns_produce_no_chunks():
    chunks = chunk_meetings([_meeting([{"speaker": "A", "text": "   "}])])
    assert chunks == []
