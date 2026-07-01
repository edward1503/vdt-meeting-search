# VimQA Semantic Metadata Sample Queries

File này liệt kê các query mẫu để test `Semantic Metadata` mode trên dataset
`VimQA Retrieval Proxy`. Các query bên dưới bám theo metadata synthetic thật đã
được tạo trong `artifacts/vimqa/all/metadata/docs-00000.jsonl`, nên phù hợp để
đối chiếu `effective_query`, `metadata_filters`, UID và metadata của retrieved
doc trên frontend.

## Cách Test Trên UI

1. Mở `http://localhost:3001`.
2. Chọn dataset `VimQA Retrieval Proxy`.
3. Chọn method `Standard BM25 (Keyword Only)` để test parser/filter rõ nhất.
4. Chọn search mode `Semantic Metadata`.
5. Dán một query mẫu bên dưới và bấm `Search Results`.
6. Đối chiếu dòng result header: `UID`, `Author`, `Created`, `Modified`,
   `Split`, và `Score`.

## Query Mẫu Đã Verify Nên Có Kết Quả

### 1. Điện Ảnh, Author + Created Before

```text
tài liệu về điện ảnh của Nguyen An trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = điện ảnh
author = Nguyen An
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_56005ae161eac1e9
Author = Nguyen An
Created = 2024-01-01
Modified = 2024-01-02
Split = train
```

### 2. Điện Ảnh, Author + Modified After

```text
văn bản về điện ảnh bởi Nguyen An chỉnh sửa sau 2024-01-01
```

Kỳ vọng parser:

```text
effective_query = điện ảnh
author = Nguyen An
modified_at_from = 2024-01-01
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_56005ae161eac1e9
Author = Nguyen An
Created = 2024-01-01
Modified = 2024-01-02
Split = train
```

### 3. Nobel Hóa Học, Author + Created Before

```text
tài liệu về Nobel Hóa học của Nguyen Binh trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = Nobel Hóa học
author = Nguyen Binh
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_5ec50b93d1c4d502
Author = Nguyen Binh
Created = 2024-01-02
Modified = 2024-01-03
Split = train
```

### 4. Nhạc Đồng Quê, Author + Created Before

```text
tài liệu về nhạc đồng quê của Nguyen Chau trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = nhạc đồng quê
author = Nguyen Chau
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_df1c603c851566c8
Author = Nguyen Chau
Created = 2024-01-03
Modified = 2024-01-04
Split = train
```

### 5. Quyền Trẻ Em, Author + Created Before

```text
tài liệu về quyền trẻ em của Nguyen Dat trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = quyền trẻ em
author = Nguyen Dat
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_0fe7ea9cbb6b1144
Author = Nguyen Dat
Created = 2024-01-04
Modified = 2024-01-05
Split = train,test
```

### 6. Kon Tum, Author + Created Before

```text
văn bản về Kon Tum bởi Nguyen Giang trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = Kon Tum
author = Nguyen Giang
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_da81df117eed70a2
Author = Nguyen Giang
Created = 2024-01-05
Modified = 2024-01-06
Split = train,test
```

### 7. Laser Đỏ, Author + Modified After

```text
văn bản về laser đỏ bởi Nguyen Ha chỉnh sửa sau 2024-01-05
```

Kỳ vọng parser:

```text
effective_query = laser đỏ
author = Nguyen Ha
modified_at_from = 2024-01-05
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_60e5ef6113a1509f
Author = Nguyen Ha
Created = 2024-01-06
Modified = 2024-01-07
Split = train
```

### 8. Manchester City, Author + Created Before

```text
tài liệu về Manchester City của Nguyen Hieu trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = Manchester City
author = Nguyen Hieu
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_35b4a84a5ec32e44
Author = Nguyen Hieu
Created = 2024-01-08
Modified = 2024-01-09
Split = train
```

### 9. Real Madrid, Author + Created Before

```text
tài liệu về Real Madrid của Nguyen Khanh trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = Real Madrid
author = Nguyen Khanh
created_at_to = 2024-01-31
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_2aa0375e000d715b
Author = Nguyen Khanh
Created = 2024-01-10
Modified = 2024-01-11
Split = train
```

### 10. Bóng Đá Ý, Author + Modified After

```text
văn bản về bóng đá Ý bởi Nguyen Long chỉnh sửa sau 2024-01-13
```

Kỳ vọng parser:

```text
effective_query = bóng đá Ý
author = Nguyen Long
modified_at_from = 2024-01-13
```

Kỳ vọng result top:

```text
UID = vimqa_ctx_b6c169fd43195274
Author = Nguyen Long
Created = 2024-01-13
Modified = 2024-01-14
Split = train
```

## Query Âm Tính Để Kiểm Tra Filter

Query này parser vẫn tách được metadata, nhưng có thể trả ít hoặc không có kết
quả vì author/date không khớp với nội dung mong muốn:

```text
tài liệu về điện ảnh của Tran Minh trước 31/01/2024
```

Kỳ vọng parser:

```text
effective_query = điện ảnh
author = Tran Minh
created_at_to = 2024-01-31
```

Nếu kết quả rỗng, đó là filter đang hoạt động: query yêu cầu đúng nội dung
`điện ảnh` nhưng giới hạn vào author/date khác với doc mẫu đầu tiên.

## Ghi Chú

- Metadata này là synthetic metadata để demo thuật toán, không phải metadata
  gốc thật của VimQA.
- `semantic_metadata=true` chỉ bật parser; metadata vẫn đi qua Elasticsearch
  filter cứng (`hard_prefilter`).
- Khi test semantic metadata, ưu tiên `es_bm25` trước. Sau khi parser/filter rõ
  ràng rồi mới thử `es_hybrid` hoặc `es_dense`.
