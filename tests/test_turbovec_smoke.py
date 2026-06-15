from __future__ import annotations

import numpy as np


def test_turbovec_id_map_add_search_and_load(tmp_path):
    from turbovec import IdMapIndex

    rng = np.random.default_rng(13)
    vectors = rng.normal(size=(100, 384)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ids = np.arange(1000, 1100, dtype=np.uint64)

    index = IdMapIndex(dim=384, bit_width=4)
    index.add_with_ids(vectors, ids)

    scores, result_ids = index.search(vectors[7:8], k=3)
    assert scores.shape == (1, 3)
    assert result_ids[0, 0] == 1007

    path = tmp_path / "smoke.tvim"
    index.write(str(path))
    loaded = IdMapIndex.load(str(path))
    loaded_scores, loaded_ids = loaded.search(vectors[7:8], k=3)
    assert loaded_ids[0, 0] == 1007
    assert loaded_scores.shape == (1, 3)
