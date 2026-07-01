# Semantic Metadata Search Algorithm

## Mục Tiêu

Semantic metadata search trong Sprint 5 cho phép người dùng viết metadata
constraint trực tiếp trong câu query tự nhiên, thay vì phải nhập riêng từng ô
filter. Hệ thống tách query thành hai phần:

```text
content intent       -> dùng để retrieve nội dung
metadata constraints -> dùng làm structured Elasticsearch filter
```

Ví dụ VimQA:

```text
tài liệu về điện ảnh của Nguyen An trước 31/01/2024
```

được hiểu thành:

```text
effective_query = điện ảnh
metadata_filters.author = Nguyen An
metadata_filters.created_at_to = 2024-01-31
```

Điểm quan trọng: metadata không được nối vào text để embed. Metadata vẫn là
field có cấu trúc (`author`, `created_at`, `modified_at`) và được áp bằng
filter cứng trong retrieval.

## Phạm Vi Dữ Liệu

Hệ thống áp dụng cùng một contract cho HotpotQA và VimQA:

| Dataset | Metadata fields | Ghi chú |
| --- | --- | --- |
| HotpotQA | `author`, `created_at`, `modified_at` | Synthetic metadata đã tạo cho toàn bộ 5,233,329 docs ở artifact disk. Active ES index cần được backfill metadata để filter có kết quả. |
| VimQA | `author`, `created_at`, `modified_at`, thêm `source_split`/`answer` khi có | Synthetic metadata đã tạo cho toàn bộ 3,623 docs VimQA và đã backfill vào live ES runtime. |

Metadata là synthetic operational metadata để demo thuật toán, không phải
metadata gốc thật của dataset.

## API Contract

Parser chỉ chạy khi request bật:

```json
{
  "query": "tài liệu về điện ảnh của Nguyen An trước 31/01/2024",
  "method": "es_bm25",
  "top_k": 5,
  "semantic_metadata": true
}
```

Nếu `semantic_metadata=false`, search cũ giữ nguyên: query được gửi trực tiếp
vào retriever và chỉ dùng manual metadata filters nếu UI/API truyền rõ ràng.

Response semantic metadata có thêm các field giải thích:

```json
{
  "query": "tài liệu về điện ảnh của Nguyen An trước 31/01/2024",
  "effective_query": "điện ảnh",
  "semantic_metadata": true,
  "metadata_filters": {
    "author": "Nguyen An",
    "created_at_to": "2024-01-31"
  },
  "metadata_filter_scope": "hard_prefilter",
  "parsed_query": {
    "content_query": "điện ảnh",
    "parsed_chips": [
      "Content: điện ảnh",
      "Created before: 2024-01-31",
      "Author: Nguyen An"
    ],
    "parsed": true,
    "parser": "rule_based"
  }
}
```

## Thuật Toán

### 1. Nhận Diện Semantic Frame

Parser chỉ nhận các query có frame rõ ràng. Điều này giảm false positive với
các câu hỏi QA thông thường.

Frame tiếng Anh:

```text
documents about <topic>
documents related to <topic>
find documents about <topic>
search documents about <topic>
```

Frame tiếng Việt:

```text
tài liệu về <topic>
văn bản về <topic>
```

Nếu không có frame, parser trả:

```text
parsed = false
content_query = original_query
metadata_filters = {}
```

### 2. Tách Date Constraint

Parser tìm các cụm date trong phần còn lại của query và normalize về ISO date
`YYYY-MM-DD`.

Các pattern đang support:

| Pattern | Filter |
| --- | --- |
| `before <date>` | `created_at_to` |
| `after <date>` | `created_at_from` |
| `created before <date>` | `created_at_to` |
| `created after <date>` | `created_at_from` |
| `modified before <date>` | `modified_at_to` |
| `modified after <date>` | `modified_at_from` |
| `trước <date>` | `created_at_to` |
| `sau <date>` | `created_at_from` |
| `chỉnh sửa trước <date>` | `modified_at_to` |
| `chỉnh sửa sau <date>` | `modified_at_from` |

Date format hỗ trợ:

```text
2024-01-31
01/31/2024
31/01/2024
```

### 3. Tách Author Constraint

Parser tìm author sau các cue sau:

```text
by <author>
written by <author>
authored by <author>
của <author>
bởi <author>
```

Author chỉ được nhận nếu khớp danh sách synthetic author đã biết trong
`DISPLAY_AUTHORS`. Nếu có cue author nhưng tên không khớp danh sách, parser
không tạo filter author và trả warning:

```text
Author phrase was present but did not match known synthetic authors.
```

### 4. Tạo Effective Query

Sau khi remove date phrase và author phrase, phần còn lại được clean thành
`content_query`. Đây là query thật được gửi vào retriever.

Ví dụ:

```text
original_query  = văn bản về giáo dục bởi Tran Minh chỉnh sửa sau 2024-02-03
content_query   = giáo dục
metadata filter = author: Tran Minh, modified_at_from: 2024-02-03
```

Nếu parser tách được metadata nhưng không còn content ổn định, hệ thống fallback
về original query và trả warning để tránh search query rỗng.

### 5. Merge Với Manual Filters

API tạo `SearchExecutionPlan`:

```text
original_query = request.query
effective_query = parsed.content_query
metadata_filters = parsed.metadata_filters + manual_filters
```

Manual filter từ UI/API có quyền override parsed filter. Lý do: khi người dùng
đã điền ô filter rõ ràng, lựa chọn explicit đó nên ưu tiên hơn parser.

### 6. Route Retrieval Method

API dùng `effective_query` để search và dùng `metadata_filters` để constrain
candidate/result set.

| Method | Semantic metadata behavior |
| --- | --- |
| `es_bm25` | Query nội dung đi vào BM25; metadata đi vào Elasticsearch `bool.filter`. |
| `es_dense` | Dense query dùng `effective_query`; metadata support phụ thuộc retriever/index path. |
| `es_hybrid` | BM25 side nhận metadata filter, sau đó fuse BM25 + dense bằng RRF. |
| `tv_hybrid` | Nếu có metadata filter thì API tự route sang `tv_filtered_hybrid`. |
| `tv_dense` | Reject khi có metadata filter vì dense-only không có structured prefilter trong contract hiện tại. |

### 7. Elasticsearch Filter

Metadata filter được build thành filter context, không ảnh hưởng score BM25:

```json
{
  "query": {
    "bool": {
      "must": [
        { "multi_match": { "query": "điện ảnh", "fields": ["title^2", "content"] } }
      ],
      "filter": [
        { "term": { "author": "Nguyen An" } },
        { "range": { "created_at": { "lte": "2024-01-31" } } }
      ]
    }
  }
}
```

Vì nằm trong `filter`, metadata constraint là hard prefilter:

```text
doc không khớp metadata -> bị loại
doc khớp metadata -> được rank theo content score
```

## UI Flow

Trên frontend:

1. Người dùng chọn dataset HotpotQA hoặc VimQA.
2. Chọn `Search Mode = Semantic Metadata`.
3. UI gửi `semantic_metadata: true` trong POST body.
4. UI hiển thị `Parsed Query` chips từ `parsed_query.parsed_chips`.
5. Result card hiển thị metadata thực tế của retrieved doc/chunk cạnh UID/Score:

```text
UID: vimqa_ctx_56005ae161eac1e9
Author: Nguyen An
Created: 2024-01-01
Modified: 2024-01-02
Split: train
Score: 8.1887
```

Nhờ đó có thể đối chiếu trực tiếp:

```text
parsed filter yêu cầu Author = Nguyen An
retrieved doc hiển thị Author = Nguyen An
```

## Ví Dụ VimQA

Input:

```text
tài liệu về điện ảnh của Nguyen An trước 31/01/2024
```

Execution:

```text
semantic_metadata = true
effective_query = điện ảnh
metadata_filters.author = Nguyen An
metadata_filters.created_at_to = 2024-01-31
method = es_bm25
metadata_filter_scope = hard_prefilter
```

Expected result đã dùng để smoke test:

```text
UID = vimqa_ctx_56005ae161eac1e9
Author = Nguyen An
Created = 2024-01-01
Modified = 2024-01-02
Split = train
```

Thêm query mẫu nằm ở:

```text
docs/sprint5/vimqa-semantic-metadata-sample-queries.md
```

## Ví Dụ HotpotQA

Input:

```text
find documents about anarchism by Nguyen An before 01/31/2024
```

Execution:

```text
semantic_metadata = true
effective_query = anarchism
metadata_filters.author = Nguyen An
metadata_filters.created_at_to = 2024-01-31
method = es_bm25
metadata_filter_scope = hard_prefilter
```

Expected smoke result:

```text
UID = 12
Title = Anarchism
Author = Nguyen An
Created = 2024-01-01
Modified = 2024-01-02
```

## Vì Sao Không Embed Metadata?

Không append metadata vào `embedding_text` vì metadata ở đây là field vận hành,
không phải nội dung semantic của document. Nếu embed các token như author/date,
dense retrieval sẽ học tín hiệu nhân tạo và làm vector content kém sạch hơn.

Thiết kế hiện tại tách rõ:

```text
content text       -> BM25 / dense embedding
metadata fields    -> structured filter
parser explanation -> parsed chips / debug fields
```

## Validation

Các test liên quan:

```text
python -m pytest tests/test_metadata_query_parser.py tests/test_semantic_metadata_api.py -q
python -m pytest tests/test_search_ui_metadata.py -q
```

Các điểm được test:

- English HotpotQA semantic query parsing.
- Vietnamese VimQA semantic query parsing.
- Manual filters override parsed filters.
- API trả `effective_query`, `metadata_filters`, `parsed_query`.
- UI có toggle `Semantic Metadata`, parsed chips, highlight theo
  `effective_query`, và metadata result chips.

## Runtime Notes Và Giới Hạn

- Parser hiện là deterministic rule-based parser, không phải LLM parser.
- Chỉ support các frame/pattern đã liệt kê; query quá tự do có thể không parse.
- Semantic metadata search chỉ có kết quả nếu active Elasticsearch index có
  mapping và dữ liệu cho `author`, `created_at`, `modified_at`.
- HotpotQA synthetic metadata artifact đã có đủ 5,233,329 docs trên disk, nhưng
  active full ES index cần backfill metadata để semantic filter hoạt động trên
  toàn corpus.
- VimQA live runtime đã được backfill toàn bộ 3,623 docs trong phiên debug hiện
  tại.
- Metadata synthetic chỉ phục vụ demo/algorithm evidence, không nên trình bày
  như production meeting metadata.
