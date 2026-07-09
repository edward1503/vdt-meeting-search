# VimQA Semantic Metadata Search Report

## Scope

This Sprint 5 update extends the existing HotpotQA semantic metadata search
design to VimQA. The goal is not to create a separate VimQA retrieval system;
it is to reuse the same opt-in query-understanding contract:

```text
semantic_metadata=true
  -> parse natural-language query
  -> preserve original_query
  -> derive effective_query
  -> derive metadata_filters
  -> route through the existing metadata-aware retrieval path
  -> return parsed_query chips for explanation
```

VimQA now has an offline synthetic metadata artifact under
`artifacts/vimqa/all/metadata` with `author`, `created_at`, and `modified_at`.
The semantic search layer uses those same structured fields. It does not append
metadata to `embedding_text`, and it does not train or call a generative parser.

## Algorithm

### 1. Parse Only When Opted In

Standard search remains unchanged. The parser runs only when the API request has
`semantic_metadata=true`.

For a VimQA-style query:

```text
tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024
```

the parser produces:

```json
{
  "original_query": "tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024",
  "content_query": "lịch sử Việt Nam",
  "metadata_filters": {
    "author": "Nguyen An",
    "created_at_to": "2024-01-31"
  },
  "parsed_chips": [
    "Content: lịch sử Việt Nam",
    "Created before: 2024-01-31",
    "Author: Nguyen An"
  ],
  "parsed": true,
  "parser": "rule_based"
}
```

The same parser still supports the existing English HotpotQA forms, for example
`documents about anarchism by Nguyen An before 01/31/2024`.

### 2. Recognize Query Frames

The deterministic parser first checks for an explicit semantic metadata search
frame. The supported frames are intentionally narrow to avoid false positives in
ordinary QA questions.

English frames:

```text
documents about <topic>
documents related to <topic>
```

Vietnamese frames:

```text
tài liệu về <topic>
văn bản về <topic>
```

If no frame is found, the parser returns `parsed=false`, leaves the content query
unchanged, and applies no metadata filters.

### 3. Extract Metadata Constraints

After the frame is removed, the parser strips recognized metadata expressions
from the remaining query body.

Author cues:

```text
by <known synthetic author>
written by <known synthetic author>
authored by <known synthetic author>
của <known synthetic author>
bởi <known synthetic author>
```

Date cues:

```text
before <date>                  -> created_at_to
after <date>                   -> created_at_from
created before/after <date>    -> created_at_to/from
modified before/after <date>   -> modified_at_to/from
trước <date>                   -> created_at_to
sau <date>                     -> created_at_from
chỉnh sửa trước/sau <date>     -> modified_at_to/from
```

Supported date formats are ISO dates and slash dates:

```text
2024-01-31
01/31/2024
31/01/2024
```

Slash dates are normalized to ISO `YYYY-MM-DD` before they reach the retriever.

### 4. Build The Execution Plan

The API converts parser output into a search execution plan:

```text
original_query = request.query
effective_query = parsed.content_query
metadata_filters = parsed.metadata_filters merged with manual filters
```

Manual UI filters still override parsed filters. This keeps the existing
HotpotQA contract intact and gives explicit controls priority when both are
present.

### 5. Route Through Existing Retrieval

VimQA uses the same metadata-aware Elasticsearch retriever path as HotpotQA:

- `es_bm25` receives a BM25 query plus Elasticsearch `bool.filter` clauses.
- `es_hybrid` applies the metadata filter to the BM25 candidate side, then fuses
  BM25 and dense candidates with RRF.
- Result rows can carry metadata fields back to the UI because `_source` includes
  `author`, `created_at`, and `modified_at`.

The dataset profile now marks VimQA as metadata-filter capable so parsed filters
are not rejected before retrieval.

## Why Metadata Is Not Embedded

The metadata fields are synthetic operational attributes, not document content.
Appending them to embeddings would make dense retrieval learn artificial tokens
such as author names and generated dates, which weakens the meaning of the
content vector. Keeping metadata as filters preserves a clean separation:

```text
content relevance -> BM25 / dense retrieval
metadata constraints -> structured filters
query explanation -> parsed chips
```

This matches the Sprint 5 semantic metadata design already used for HotpotQA.

## Example

Input:

```text
văn bản về giáo dục bởi Tran Minh chỉnh sửa sau 2024-02-03
```

Parsed execution:

```text
effective_query = giáo dục
metadata_filters.author = Tran Minh
metadata_filters.modified_at_from = 2024-02-03
```

The UI can display:

```text
Content: giáo dục
Author: Tran Minh
Modified after: 2024-02-03
```

## Validation

Focused validation:

```text
python -m pytest tests/test_metadata_query_parser.py tests/test_semantic_metadata_api.py -q
```

Result:

```text
10 passed, 3 warnings
```

The new tests cover:

- Vietnamese `tài liệu về ... của ... trước ...` parsing.
- Vietnamese `văn bản về ... bởi ... chỉnh sửa sau ...` parsing.
- VimQA dataset-scoped API execution using the same `semantic_metadata=true`
  contract as HotpotQA.

## Limitations

- The parser is rule-based and intentionally narrow; it is designed for stable
  demo queries, not open-ended Vietnamese language understanding.
- Live retrieval quality depends on running a VimQA Elasticsearch index that
  contains the generated metadata fields.
- This report describes synthetic metadata retrieval behavior, not a production
  meeting metadata benchmark.

## Next Step

Run a live VimQA semantic metadata smoke search against the metadata-enriched
Elasticsearch index and add a small comparison artifact analogous to the
HotpotQA semantic metadata smoke report.
