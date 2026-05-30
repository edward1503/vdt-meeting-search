# Data Processing Plan

This document translates the data-related work in `docs/plan.md` into an implementation-ready processing workflow. The project uses text-based meeting data only. Audio processing, ASR, and diarization are out of scope for the MVP.

## Goals

Prepare QMSum and AMI into one consistent representation that can support:

- content search over meeting transcript text;
- metadata filtering/search over speaker, source, meeting ID, time range, and derived topic/domain fields;
- chunk-level Elasticsearch indexing;
- meeting-level search results with evidence passages;
- evaluation using QMSum query-to-meeting relevance.

## Raw Inputs

Expected files:

```text
data/raw/QMSum-main.zip
data/raw/ami_public_manual_1.6.2.zip
```

If the files are placed directly under `data/`, move them into `data/raw/` before processing.

After unzipping the current archives, the expected extracted directories are:

```text
data/raw/QMSum-main/QMSum-main/data/
data/raw/ami_public_manual_1.6.2/
```

The processing code should accept either zip paths or these extracted directories. For local development, reading the extracted directories is simpler and easier to inspect.

QMSum is the evaluation backbone because it provides query-focused meeting data. AMI is the metadata-rich demo backbone because it provides speaker turns and time-aligned transcript annotations.

## Processed Outputs

The processing pipeline should generate these artifacts:

```text
data/processed/meetings.jsonl
data/processed/chunks.jsonl
data/processed/qmsum_queries.jsonl
data/processed/qrels.jsonl
data/processed/metadata_queries.jsonl
```

`meetings.jsonl` is the normalized meeting-level source of truth.

`chunks.jsonl` is the indexing input for Elasticsearch.

`qmsum_queries.jsonl` and `qrels.jsonl` are used for meeting-level retrieval evaluation.

`metadata_queries.jsonl` is a small multi-condition set (chủ đề + người + thời gian) for prompt NLU and separate metadata-channel evaluation.

## Unified Meeting Schema

Every dataset should be normalized into this JSONL schema:

```json
{
  "meeting_id": "string",
  "source": "qmsum|ami",
  "title": "string|null",
  "date": "string|null",
  "participants": ["string"],
  "turns": [
    {
      "speaker": "string|null",
      "text": "string",
      "time_start": 0.0,
      "time_end": 0.0
    }
  ],
  "metadata": {
    "domain": "string|null",
    "topic": "string|null",
    "is_derived_topic": true
  }
}
```

Rules:

- Missing metadata should be represented as `null` or an empty list, not guessed silently.
- Derived fields must be marked, for example `is_derived_topic: true`.
- Keep original speaker IDs when available.
- Keep timestamps when available.
- Do not lowercase all text, because names, IDs, and entities matter for search.
- Every meeting must include both `meeting_id` and `raw_meeting_id`. Use source-prefixed IDs for `meeting_id`, for example `qmsum_ES2004a` or `ami_ES2004a`.

## QMSum Processing

Use QMSum first because it gives the retrieval evaluation set.

Expected responsibilities:

- read `QMSum-main.zip` locally or the extracted `data/raw/QMSum-main/QMSum-main/` directory;
- use `data/ALL/train`, `data/ALL/val`, and `data/ALL/test` as the canonical meeting source;
- do not parse `ALL` plus `Academic`/`Product`/`Committee` as separate corpora, because the category folders duplicate the same meetings by domain;
- optionally build a domain map by scanning filenames under `Academic`, `Product`, and `Committee`;
- create normalized meeting records with `source: "qmsum"`;
- extract natural-language queries;
- create one qrel per query where the source meeting is relevant.

Observed QMSum structure:

```text
data/ALL/train/*.json      canonical train meetings
data/ALL/val/*.json        canonical validation meetings
data/ALL/test/*.json       canonical test meetings
data/ALL/jsonl/*.jsonl     same split data in JSONL form
data/Academic/...          domain-specific duplicate subset
data/Product/...           domain-specific duplicate subset
data/Committee/...         domain-specific duplicate subset
```

Each meeting JSON has these useful fields:

```text
meeting_transcripts[]: speaker, content
specific_query_list[]: query, answer, relevant_text_span
general_query_list[]: query, answer
topic_list[]: topic, relevant_text_span
```

Use both `specific_query_list` and `general_query_list` for evaluation queries. Keep `relevant_text_span` when available, but treat it as weak evidence-span metadata. It is not a chunk-level label until the span has been mapped to normalized turns/chunks and manually spot-checked.

QMSum relevant spans are useful for later passage evaluation, but the MVP meeting-level evaluation should use query-to-source-meeting qrels.

Recommended query schema:

```json
{
  "query_id": "qmsum_product_0001_q000",
  "query": "What did the team decide about the remote control design?",
  "source": "qmsum",
  "meeting_id": "qmsum_ES2004a",
  "raw_meeting_id": "ES2004a",
  "split": "test",
  "query_type": "specific"
}
```

Recommended qrel schema:

```json
{
  "query_id": "qmsum_product_0001_q000",
  "meeting_id": "qmsum_ES2004a",
  "relevance": 1
}
```

Evaluation interpretation:

```text
QMSum query -> source meeting_id is relevant
```

This is a meeting-level relevance label. It does not prove passage-level evidence quality, so a small manual passage set can be added later as a should-have item.

## AMI Processing

Use AMI for transcript text, speaker turns, and time metadata.

Expected responsibilities:

- read `ami_public_manual_1.6.2.zip` locally or the extracted `data/raw/ami_public_manual_1.6.2/` directory;
- parse `corpusResources/meetings.xml` for meeting metadata, speaker global IDs, speaker roles, dates, and durations;
- parse `words/*.words.xml` for token text and token timestamps;
- parse `segments/*.segments.xml` for utterance/segment boundaries over word ID ranges;
- group utterances by `meeting_id`;
- map filename speaker agents such as `A`, `B`, `C`, `D`, `E` to `global_name` and role through `meetings.xml` when available;
- preserve speaker ID, agent label, role, utterance text, start time, and end time when available;
- create normalized meeting records with `source: "ami"`.

Observed AMI structure:

```text
corpusResources/meetings.xml       meeting date/duration + speaker mapping
words/{meeting}.{agent}.words.xml  word tokens with start/end times
segments/{meeting}.{agent}.segments.xml  segment ranges pointing to word IDs
abstractive/*.abssumm.xml          optional summaries
topics/*.topic.xml                 topic spans/pointers, optional for MVP
```

The MVP parser should use `meetings.xml`, `words`, and `segments`. Topic and abstractive summary files are useful later, but they are not required for the first processed dataset.

AMI parser implementation notes:

- XML uses namespaces; parse by local tag name or namespace-aware queries.
- `words/*.words.xml` contains word tokens in `<w>` elements and may also contain non-word markers such as disfluency markers. Skip non-word markers for transcript text.
- Punctuation tokens have `punc="true"`; attach punctuation without adding an extra leading space.
- `segments/*.segments.xml` contains `nite:child href` references to either one word ID or a word ID range such as `id(ES2004a.A.words2)..id(ES2004a.A.words13)`.
- Segment text should be reconstructed by joining the referenced word tokens from the corresponding words file.
- Segment time should prefer `transcriber_start` and `transcriber_end`; fallback to min/max referenced word start/end times when segment times are missing.
- Merge all speaker-agent segment files for a meeting and sort reconstructed turns by `time_start`.
- Map filename agent labels such as `A`, `B`, `C`, `D`, `E` through `corpusResources/meetings.xml` to `global_name` and role.
- Normalize `dateOnly="29-10-2004"` to `date: "2004-10-29"` when possible, and normalize `startTime="10h46"` to `start_time: "10:46"`.

Recommended AMI meeting example:

```json
{
  "meeting_id": "ami_ES2002a",
  "source": "ami",
  "title": "AMI ES2002a",
  "date": "2004-10-29",
  "start_time": "10:46",
  "participants": ["MIO016", "MIO082"],
  "turns": [
    {
      "speaker": "MIO016",
      "speaker_agent": "A",
      "speaker_role": "ID",
      "text": "I think we should use a simple interface.",
      "time_start": 12.35,
      "time_end": 18.92
    }
  ],
  "metadata": {
    "domain": "ami",
    "topic": null,
    "is_derived_topic": false
  }
}
```

## Cleaning Rules

Cleaning should be conservative:

- normalize whitespace;
- remove empty turns;
- strip XML markup and annotation artifacts;
- keep speaker names/IDs;
- keep original casing;
- keep timestamps;
- avoid stemming, paraphrasing, summarizing, or LLM-based rewriting.

The goal is to preserve evidence quality. Search results should be able to show a retrieved chunk as a faithful passage from the source meeting.

## Chunking Strategy

Index chunks, not whole meetings. Return meeting-level results by grouping retrieved chunks on `meeting_id`.

Chunking should be speaker-aware:

1. Start from normalized meeting turns.
2. Merge consecutive turns from the same speaker when practical.
3. Accumulate turns until the chunk reaches the target size.
4. Avoid cutting through a speaker turn unless the turn is too long.
5. Split long blocks with sliding windows.

Recommended settings:

```text
target_chunk_tokens: 256-384
max_chunk_tokens: 512
overlap_tokens: 50-100, only when splitting long text
```

Recommended chunk schema:

```json
{
  "chunk_id": "ami_ES2002a_00012",
  "meeting_id": "ami_ES2002a",
  "raw_meeting_id": "ES2002a",
  "source": "ami",
  "title": "AMI ES2002a",
  "text": "MIO016: I think we should use a simple interface. MIO082: Yes, but we need...",
  "speakers": ["MIO016", "MIO082"],
  "speaker_agents": ["A", "B"],
  "speaker_roles": ["ID", "PM"],
  "time_start": 12.35,
  "time_end": 48.21,
  "metadata_text": "source: ami meeting: ES2002a title: AMI ES2002a speakers: MIO016 MIO082 roles: ID PM",
  "token_count": 184
}
```

`chunk_id` should be deterministic and stable, for example:

```text
{source}_{meeting_id}_{chunk_index:05d}
```

Use source-prefixed `meeting_id` values such as `qmsum_ES2004a` and `ami_ES2004a`. QMSum contains some AMI-style meeting IDs, so source prefixing prevents collisions when QMSum and AMI are indexed together.

## Evaluation Corpus Modes

QMSum and AMI overlap on some raw meeting IDs. For example, QMSum contains AMI-style IDs such as `ES2004a`, and AMI also contains `ES2004a`.

This creates an evaluation trap: a QMSum query whose qrel points to `qmsum_ES2004a` may retrieve `ami_ES2004a`. The result can be semantically correct but counted as false if the qrels only contain the QMSum-prefixed meeting.

To avoid misleading metrics, support two modes:

```text
eval_qmsum: index/search only QMSum meetings, evaluate with QMSum qrels
demo_full: index/search QMSum + AMI together for demo and metadata search
```

For the MVP report, use `eval_qmsum` as the primary retrieval benchmark and `demo_full` for user-facing demo behavior.

## Metadata Representation

The MVP uses:

- `text` / `content_text` for BM25 and highlighting;
- `metadata_text` for BM25 metadata matching;
- structured fields for exact filtering;
- `content_embedding = embed(text)` for dense retrieval over content;
- `metadata_embedding = embed(metadata_text)` for dense retrieval over metadata.

README yêu cầu "vector embeddings cho cả nội dung và metadata", nên pipeline tạo **cả hai** embedding. `metadata_text` được xây từ các trường có ngữ nghĩa (title, speakers, role, date, source, topic) — không chỉ ID thuần — để metadata embedding có giá trị. Structured fields vẫn dùng cho exact filtering; đóng góp thực tế của metadata embedding được đo bằng đánh giá theo-nguồn (xem mục Metadata Query Set).

## Metadata Query Set

Tạo file nhỏ `data/processed/metadata_queries.jsonl` để kiểm tra **prompt NLU đa điều kiện** và đánh giá riêng kênh metadata (README: truy vấn nhiều điều kiện theo chủ đề + người + thời gian; đánh giá riêng từng nguồn).

Recommended schema:

```json
{
  "query_id": "meta_ami_001",
  "query": "Find AMI meetings led by the project manager about interface design in 2005",
  "expected_filters": {
    "source": "ami",
    "speaker_role": "PM",
    "date_range": ["2005-01-01", "2005-12-31"]
  },
  "relevant_meeting_ids": ["ami_ES2002a"]
}
```

Bắt đầu nhỏ (10–20 truy vấn). Sinh từ chunk thật, không bịa: lấy 1 chunk AMI có speaker/role/time rõ → trích keyword → tạo câu hỏi tự nhiên → đặt cuộc họp liên quan = cuộc họp của chunk đó. Bao phủ các trường hợp:

- chủ đề (topic) đơn thuần;
- người tham gia (speaker/role) đơn thuần;
- thời gian (date/range) đơn thuần;
- kết hợp chủ đề + người + thời gian;
- truy vấn mơ hồ (không áp hard filter).

## Processing Command

The final processing entry point should look like this:

```powershell
python -m src.preprocessing.prepare_data `
  --qmsum-zip data/raw/QMSum-main.zip `
  --ami-zip data/raw/ami_public_manual_1.6.2.zip `
  --out-dir data/processed
```

For the current extracted local data, the command can instead use directories:

```powershell
python -m src.preprocessing.prepare_data `
  --qmsum-dir data/raw/QMSum-main/QMSum-main/data `
  --ami-dir data/raw/ami_public_manual_1.6.2 `
  --out-dir data/processed
```

The command should:

1. validate input zip files exist;
2. create `data/processed/` if needed;
3. parse QMSum;
4. parse AMI;
5. write `meetings.jsonl`;
6. write `qmsum_queries.jsonl`;
7. write `qrels.jsonl`;
8. generate chunks;
9. write `chunks.jsonl`.

## Validation Checks

After processing, run basic checks before indexing:

- `meetings.jsonl` exists and has records from both `qmsum` and `ami`;
- every meeting has `meeting_id`, `source`, and non-empty `turns`;
- `chunks.jsonl` exists and every chunk has non-empty `text`;
- every chunk has a valid `meeting_id` that appears in `meetings.jsonl`;
- QMSum queries have matching qrels;
- AMI chunks preserve speaker IDs when available;
- AMI chunks preserve `time_start` and `time_end` when available;
- QMSum evaluation can run in `eval_qmsum` mode without AMI records in the candidate set;
- overlapping `raw_meeting_id` values across sources are source-prefixed and do not collide;
- no chunk exceeds the configured maximum by a large margin;
- generated files are deterministic across repeated runs.

Minimum MVP acceptance criteria:

```text
meetings.jsonl contains QMSum and AMI records
chunks.jsonl contains indexable chunk records
qmsum_queries.jsonl contains natural-language queries
qrels.jsonl maps each QMSum query to a relevant meeting
```

## Relationship to Indexing

The processing pipeline should stop at JSONL artifacts. Elasticsearch indexing is a separate stage.

Indexing consumes `chunks.jsonl` and creates fields equivalent to:

```text
content_text/text -> BM25 + highlight
metadata_text -> BM25 metadata matching
content_embedding -> dense vector kNN (content)
metadata_embedding -> dense vector kNN (metadata)
meeting_id/source/speakers/speaker_roles/date/time_start/time_end -> structured filters
```

Keeping processing separate from indexing makes evaluation, debugging, and reruns easier.

## Out of Scope

The MVP should not include:

- audio download or processing;
- speech-to-text transcription;
- diarization;
- LLM-based data cleaning.

## Implementation Order

Recommended order:

1. Move zip files into `data/raw/`.
2. Implement QMSum local zip parser.
3. Generate QMSum meetings, queries, and qrels.
4. Implement AMI local zip parser.
5. Generate normalized AMI meetings.
6. Implement shared cleaning utilities.
7. Implement speaker-aware chunking.
8. Generate `chunks.jsonl`.
9. Add validation checks.
10. Only then implement Elasticsearch mapping and indexing.
