from __future__ import annotations

import json
import numpy as np

from scripts import embed_hotpotqa


def test_write_embedding_shard_saves_vectors_ids_and_meta(tmp_path):
    staging_file = tmp_path / "docs-00000.jsonl"
    staging_file.write_text(
        "\n".join(
            [
                json.dumps({"numeric_id": 10, "embedding_text": "alpha"}),
                json.dumps({"numeric_id": 11, "embedding_text": "beta"}),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    class FakeModel:
        def encode(self, texts, normalize_embeddings, convert_to_numpy, batch_size):
            assert texts == ["alpha", "beta"]
            assert normalize_embeddings is True
            assert convert_to_numpy is True
            assert batch_size == 2
            return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    out_dir = tmp_path / "embeddings"
    embed_hotpotqa.write_embedding_shard(staging_file, out_dir, FakeModel(), batch_size=2, model_name="fake")

    assert np.load(out_dir / "docs-00000.float16.npy").dtype == np.float16
    assert np.load(out_dir / "docs-00000.ids.npy").tolist() == [10, 11]
    meta = json.loads((out_dir / "docs-00000.meta.json").read_text(encoding="utf-8"))
    assert meta["docs"] == 2
    assert meta["dims"] == 2
    assert meta["model"] == "fake"
