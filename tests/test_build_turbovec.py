from __future__ import annotations

import numpy as np

from scripts import build_turbovec


def test_embedding_shards_are_loaded_as_float32_and_uint64(tmp_path):
    emb_dir = tmp_path / "embeddings"
    emb_dir.mkdir()
    np.save(emb_dir / "docs-00000.float16.npy", np.array([[1, 0], [0, 1]], dtype=np.float16))
    np.save(emb_dir / "docs-00000.ids.npy", np.array([5, 6], dtype=np.uint64))

    shards = list(build_turbovec.iter_embedding_shards(emb_dir))
    vectors, ids = build_turbovec.load_embedding_shard(shards[0])

    assert vectors.dtype == np.float32
    assert ids.dtype == np.uint64
    assert ids.tolist() == [5, 6]
