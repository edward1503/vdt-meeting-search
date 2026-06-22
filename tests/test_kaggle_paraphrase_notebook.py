from pathlib import Path
import json


def _notebook_text():
    path = Path('notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb')
    data = json.loads(path.read_text(encoding='utf-8'))
    lines = []
    for cell in data.get('cells', []):
        lines.extend(cell.get('source', []))
    return '\n'.join(lines)


def _notebook_code_cell(cell_id):
    path = Path('notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb')
    data = json.loads(path.read_text(encoding='utf-8'))
    for cell in data.get('cells', []):
        if cell.get('id') == cell_id:
            return ''.join(cell.get('source', []))
    raise AssertionError(f'missing notebook cell: {cell_id}')


def test_kaggle_paraphrase_notebook_contract():
    path = Path('notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb')
    assert path.exists()
    text = _notebook_text()
    assert 'natural_mild' in text
    assert 'natural_strong' in text
    assert 'lexical_strong' in text
    assert '1 paraphrase per profile' in text
    assert 'source_query_id' in text
    assert 'original_query' in text
    assert 'query_id' in text
    assert 'support_doc_ids' in text
    assert 'paraphrase_profile' in text
    assert 'candidate_index' in text
    assert 'variant_query_id' in text
    assert 'paraphrased_query' in text
    assert 'openai_paraphrase_candidates.tsv' in text
    assert 'openai_paraphrase_candidates.jsonl' in text
    assert 'openai_paraphrase_shortages.tsv' in text
    assert 'openai_paraphrase_shortages.jsonl' in text
    assert 'paraphrase_checkpoints' in text
    assert 'from tqdm.auto import tqdm' in text
    assert 'from openai import OpenAI' in text
    assert 'OPENAI_API_KEY' in text
    assert 'OPENAI_BASE_URL' in text
    assert 'REPO_ROOT = find_repo_root()' in text
    assert "RUN_DIR = REPO_ROOT / 'artifacts' / 'hotpotqa_full' / 'paraphrase' / 'openai_generation'" in text
    assert "DOTENV_PATH = REPO_ROOT / '.env'" in text
    assert 'def load_repo_dotenv' in text
    assert 'load_repo_dotenv()' in text
    assert 'openai_base_url = os.environ.get' in text
    assert 'client = OpenAI(base_url=openai_base_url)' in text
    assert 'client.chat.completions.create' in text
    assert 'response.choices[0].message.content' in text
    assert 'client.responses.create' not in text
    assert "OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'combo')" in text
    assert 'CANDIDATES_PER_QUERY = 1' in text
    assert "GENERATION_PROFILES = ['natural_mild', 'natural_strong', 'lexical_strong']" in text
    assert '2-3 non-entity content words' in text
    assert 'Do not only reorder the original words' in text
    assert "for profile in GENERATION_PROFILES:" in text
    assert "print(f'Generating profile: {profile}')" in text
    assert 'SEQUENTIAL_BY_PROFILE = True' in text
    assert 'import subprocess' not in text
    assert 'paraphrase_worker.py' not in text
    assert 'subprocess.Popen' not in text
    assert 'PARALLEL_BY_PROFILE' not in text
    assert 'multiprocessing' not in text
    assert 'ctx.Process' not in text
    assert 'Qwen/' not in text
    assert 'MODEL_PRESETS' not in text
    assert 'usecols=' in text
    assert 'nrows=SOURCE_QUERY_LIMIT' in text
    assert 'dtype=str' in text
    assert 'keep_default_na=False' in text
    assert 'json.loads' in text
    assert 'parse_candidate_list' in text
    assert "'fork' in mp.get_all_start_methods()" not in text
    assert "mp.get_context('fork')" not in text
    assert 'pip install -q openai pandas tqdm' in text
    assert 'transformers' not in text
    assert 'torch' not in text
    assert 'import numpy as np' in text
    assert 'SOURCE_QUERY_LIMIT = 200' in text
    assert 'hotpotqa_full_dev_queries.tsv' in text
    assert 'REGENERATION_INPUT_TSV' in text
    assert 'REGENERATION_MODE' in text
    assert 'regeneration_needed.tsv' in text
    assert 'openai_paraphrase_regeneration_candidates.tsv' in text
    assert 'openai_paraphrase_regeneration_shortages.tsv' in text
    assert 'REGENERATION_RUN_TAG' in text
    assert "os.environ.get('PARAPHRASE_REGENERATION_RUN_TAG'" in text
    assert "f'{source_query_id}__{profile}__regen{REGENERATION_RUN_TAG}_{idx}'" in text
    assert 'def classify_input_columns' in text
    assert 'def read_input_requests' in text
    assert 'def build_qrels_json' in text
    assert 'Expanded base query input into' in text
    assert 'Limiting base query input from' in text
    assert "print('input_schema:', schema_kind)" in text
    assert 'def set_all_seeds' in text
    assert 'def discover_input_tsv' in text
    assert 'def list_visible_tsvs' in text
    assert 'def find_repo_root' in text
    assert 'EXPECTED_INPUT_FILENAMES' in text
    assert 'Could not find a paraphrase export TSV with the required columns.' in text
    assert 'Visible TSVs:' in text
    assert 'def generate_candidates' in text
    assert 'def call_openai_with_retry' in text
    assert 'response.choices[0].message.content' in text
    assert 'model.generate(' not in text
    assert 'batch_decode' not in text
    assert 'pipeline(' not in text
    assert 'set_seed' not in text
    assert "Finished natural_mild before natural_strong starts." in text


def test_paraphrase_protocol_doc_exists_and_matches_pipeline():
    path = Path('docs/sprint4/paraphrase-protocol.md')
    assert path.exists()
    text = path.read_text(encoding='utf-8')
    assert '200' in text
    assert 'natural_mild' in text
    assert 'natural_strong' in text
    assert '1 paraphrase per profile' in text
    assert 'source_query_id' in text
    assert 'hotpotqa_full_dev_queries.tsv' in text
    assert '200 source queries' in text
    assert 'accepted' in text.lower()
    assert 'rejected' in text.lower()
    assert 'original_200' in text
    assert 'mild_200' in text
    assert 'strong_200' in text
    assert 'lexical_strong_200' in text
    assert 'content_change_ratio >= 0.15' in text
    assert 'content_jaccard <= 0.80' in text
    assert 'openai_paraphrase_shortages.tsv' in text
    assert 'paraphrase_checkpoints' in text
    assert 'sequential' in text.lower()
    assert 'subprocess' not in text.lower()
    assert 'OpenAI API' in text


def test_notebook_discovers_query_tsv_when_started_from_notebooks_dir(monkeypatch):
    import pandas as pd
    import re

    input_loading_code = _notebook_code_cell('input-loading')
    monkeypatch.chdir(Path('notebooks'))
    namespace = {
        'Path': Path,
        'pd': pd,
        'json': json,
        're': re,
        'EXPECTED_INPUT_FILENAMES': [
            'hotpotqa_paraphrase_requests.tsv',
            'hotpotqa_full_dev_queries.tsv',
        ],
        'SOURCE_QUERY_LIMIT': 2,
        'GENERATION_PROFILES': ['natural_mild', 'natural_strong', 'lexical_strong'],
    }

    exec(input_loading_code, namespace)

    assert namespace['input_tsv'].name == 'hotpotqa_full_dev_queries.tsv'
    assert len(namespace['requests_df']) == 6
