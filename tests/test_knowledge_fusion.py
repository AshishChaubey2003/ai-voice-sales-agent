import uuid

from api.knowledge import RetrievedChunk, gate_by_distance, rrf_fuse


def make_chunk(name: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid5(uuid.NAMESPACE_DNS, name),
        title="Doc",
        heading=name,
        content=name,
    )


def test_chunk_found_by_both_searches_ranks_first():
    a, b, c = make_chunk("a"), make_chunk("b"), make_chunk("c")

    fused = rrf_fuse(vector_hits=[a, b], keyword_hits=[c, b], top_k=3)

    assert fused[0].heading == "b"
    assert len(fused) == 3


def test_top_k_limits_number_of_results():
    hits = [make_chunk(str(i)) for i in range(6)]

    assert len(rrf_fuse(hits, [], top_k=4)) == 4
    
def test_distance_gate_drops_far_chunks_and_their_keyword_matches():
    near = make_chunk("near")
    near.vector_distance = 0.2
    far = make_chunk("far")
    far.vector_distance = 0.5
    far_keyword_match = make_chunk("far")

    vector_hits, keyword_hits = gate_by_distance([near, far], [far_keyword_match], max_distance=0.3)

    assert [hit.heading for hit in vector_hits] == ["near"]
    assert keyword_hits == []    