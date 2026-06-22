from __future__ import annotations

from pathlib import Path

import scripts.es_hotpotqa as cli
from scripts.es_hotpotqa import done_marker_path, select_pending_files


def test_create_bm25_index_can_enable_metadata_mapping(monkeypatch):
    captured = {}

    class FakeIndices:
        def exists(self, index):
            return False

        def create(self, index, body):
            captured['index'] = index
            captured['body'] = body

        def put_alias(self, index, name):
            captured['alias'] = name

    class FakeES:
        indices = FakeIndices()

    monkeypatch.setattr(cli, '_client', lambda url: FakeES())
    args = cli.argparse.Namespace(
        url='http://example.invalid:9200',
        index='idx',
        alias='alias',
        shards=2,
        reset=False,
        metadata=True,
    )

    cli.create_bm25_index(args)

    props = captured['body']['mappings']['properties']
    assert props['author'] == {'type': 'keyword'}
    assert props['created_at'] == {'type': 'date'}
    assert props['modified_at'] == {'type': 'date'}
    assert captured['body']['settings']['number_of_shards'] == 2


def test_metadata_filters_from_args_omits_empty_values():
    args = cli.argparse.Namespace(
        author='Nguyen An',
        created_at_from='2024-01-01',
        created_at_to=None,
        modified_at_from=None,
        modified_at_to='2024-02-15',
    )

    assert cli.metadata_filters_from_args(args) == {
        'author': 'Nguyen An',
        'created_at_from': '2024-01-01',
        'modified_at_to': '2024-02-15',
    }


def test_search_index_passes_metadata_filters(monkeypatch):
    captured = {}

    class FakeRetriever:
        def __init__(self, **kwargs):
            captured['init'] = kwargs

        def search(self, query, method, top_k, candidate_k=100, metadata_filters=None):
            captured['search'] = {
                'query': query,
                'method': method,
                'top_k': top_k,
                'candidate_k': candidate_k,
                'metadata_filters': metadata_filters,
            }
            return []

    monkeypatch.setattr(cli, '_client', lambda url: object())
    monkeypatch.setattr(cli, 'ElasticsearchRetriever', FakeRetriever)
    args = cli.argparse.Namespace(
        url='http://example.invalid:9200',
        index='idx',
        model='model',
        num_candidates=1000,
        method='bm25',
        query='Arthur',
        top_k=5,
        candidate_k=20,
        author='Nguyen An',
        created_at_from='2024-01-01',
        created_at_to=None,
        modified_at_from=None,
        modified_at_to=None,
    )

    cli.search_index(args)

    assert captured['search']['metadata_filters'] == {'author': 'Nguyen An', 'created_at_from': '2024-01-01'}


def test_done_marker_path_uses_staging_file_stem(tmp_path):
    assert done_marker_path(tmp_path, Path("docs-00042.jsonl")) == tmp_path / "docs-00042.done"


def test_select_pending_files_skips_done_markers_and_applies_limit(tmp_path):
    staging = tmp_path / "staging"
    progress = tmp_path / "progress"
    staging.mkdir()
    progress.mkdir()
    for name in ["docs-00000.jsonl", "docs-00001.jsonl", "docs-00002.jsonl"]:
        (staging / name).write_text("{}\n", encoding="utf-8")
    (progress / "docs-00000.done").write_text("{}", encoding="utf-8")

    selected = select_pending_files(staging, progress, max_files=1)

    assert [path.name for path in selected] == ["docs-00001.jsonl"]


def test_main_dispatches_ingest_subcommand(monkeypatch, tmp_path):
    called = {}

    def fake_ingest(args):
        called["command"] = args.command

    monkeypatch.setattr(cli, "ingest", fake_ingest)
    monkeypatch.setattr(
        "sys.argv",
        ["es_hotpotqa.py", "ingest", "--staging-dir", str(tmp_path), "--progress-dir", str(tmp_path)],
    )

    cli.main()

    assert called == {"command": "ingest"}


def test_main_dispatches_ingest_bm25_subcommand(monkeypatch, tmp_path):
    called = {}

    def fake_ingest_bm25(args):
        called["command"] = args.command

    monkeypatch.setattr(cli, "ingest_bm25", fake_ingest_bm25)
    monkeypatch.setattr(
        "sys.argv",
        ["es_hotpotqa.py", "ingest-bm25", "--staging-dir", str(tmp_path), "--progress-dir", str(tmp_path)],
    )

    cli.main()

    assert called == {"command": "ingest-bm25"}
