# HotpotQA EDA: cấu trúc dữ liệu, preprocessing và lựa chọn framework

## 1. Tóm tắt quyết định

HotpotQA trong project này nên được xử lý như một bài toán multi-hop document retrieval: mỗi query thường cần đủ 2 supporting documents, nên `Recall@k`, `nDCG@k`, `MRR@k` và đặc biệt `full_support_recall@k` quan trọng hơn `Precision@k` đơn lẻ.

- Với `nano-beir/hotpotqa`: dùng Elasticsearch BM25, BGE dense, hybrid RRF và iterative hybrid; không chunk thêm vì document ngắn.
- Với `beir/hotpotqa/*`: dùng persistent Elasticsearch index cho sparse và dense retrieval; index `title + text`, benchmark trước trên `dev`.
- Khi nâng cấp: ưu tiên hop-conditioned retrieval hoặc entity-aware query expansion vì nhiều câu hỏi bridge có hop 2 overlap lexical thấp.

## 2. Cấu trúc dữ liệu

### `nano-beir/hotpotqa`
| Object | Python type | Fields |
|---|---|---|
| document | GenericDoc | doc_id, text |
| query | GenericQuery | query_id, text |
| qrel | TrecQrel | query_id, doc_id, relevance, iteration |

Raw `query` sample:
```text
GenericQuery(query_id='5ae5669755429960a22e02ec', text='Which of the campaign that brought out the term Vichy Republican on social media was formally launched on June 16, 2015, at Trump Tower in New York City?')
```
Raw `qrel` sample:
```text
TrecQrel(query_id='5ae5669755429960a22e02ec', doc_id='49892372', relevance=1, iteration='0')
```
Raw `document` sample:
```text
GenericDoc(doc_id='974', text='Augusta Ada King-Noel, Countess of Lovelace ("née" Byron; 10 December 1815\xa0– 27 November 1852) was an English mathematician and writer, chiefly known for her work on Charles Babbage\'s proposed mechanical general-purpose computer, the Analytical Engine. She was the first to recognise that the machine had applications beyond pure calculation, and created the first algorithm intended to be carried out by such a machine. As a result, she is often regarded as the first to recognise the full potential of a "computing machine" and the first computer programmer.')
```

### `beir/hotpotqa`
Chỉ có metadata; chưa iterate raw records trong cache local.

### `beir/hotpotqa/train`
Chỉ có metadata; chưa iterate raw records trong cache local.

### `beir/hotpotqa/dev`
Chỉ có metadata; chưa iterate raw records trong cache local.

### `beir/hotpotqa/test`
Chỉ có metadata; chưa iterate raw records trong cache local.

## 3. Preview vài dòng data

Mục tiêu của phần này là nhìn trực tiếp vài row thô trước khi bàn model/index. Người đọc cần thấy rõ `query`, `qrel` và `document` nối với nhau như thế nào.

Query rows:
| query_id | text | tokens | labels |
|---|---|---|---|
| 5ae5669755429960a22e02ec | Which of the campaign that brought out the term Vichy Republican on social media was formally launched on June 16, 2015, at Tru... | 28 | which/bridge |
| 5a811667554299260e20a23d | What occupations do both Ian Hunter and Rob Thomas have? | 10 | comparison/both, what, explicit relation clue |
| 5abdf8c45542993f32c2a072 | The Death of Cook depicts the death of James Cook at a bay on what coast? | 16 | what, explicit relation clue |

Qrel/support rows:
| query_id | doc_id | relevance | meaning |
|---|---|---|---|
| 5ae5669755429960a22e02ec | 49892372 | 1 | support document |
| 5ae5669755429960a22e02ec | 46979246 | 1 | support document |
| 5a811667554299260e20a23d | 6668827 | 1 | support document |
| 5a811667554299260e20a23d | 580274 | 1 | support document |

Document rows:
| doc_id | title | tokens | text preview |
|---|---|---|---|
| 974 |  | 91 | Augusta Ada King-Noel, Countess of Lovelace ("née" Byron; 10 December 1815 – 27 November 1852) was an English mathematician and writer, chiefly kno... |
| 4009 |  | 53 | Bigfoot (also known as Sasquatch) is a cryptid which supposedly is a simian-like creature of American folklore that is said to inhabit forests, esp... |
| 4955 |  | 69 | A bokken (木剣 , "bok(u)", "wood", and "ken", "sword") (or a "bokutō" 木刀 , as they are instead called in Japan) is a Japanese wooden sword used for t... |

## 4. Nội dung dàn trải như thế nào

| Thành phần | Số lượng |
|---|---|
| Documents | 5090 |
| Queries | 50 |
| Qrels | 100 |

Document text token lengths:
| min | p50 | p90 | p95 | p99 | max | avg |
|---|---|---|---|---|---|---|
| 4 | 50 | 113 | 136 | 194 | 352 | 58.4 |

Title rỗng: `5090/5090` documents trong sample đã iterate.

Query token lengths:
| min | p50 | p90 | p95 | p99 | max | avg |
|---|---|---|---|---|---|---|
| 8 | 15 | 24 | 27 | 28 | 28 | 15.2 |

Question patterns:
| Pattern | Count |
|---|---|
| what | 21 |
| which/bridge | 13 |
| explicit relation clue | 11 |
| who | 9 |
| comparison/both | 6 |
| other | 3 |
| where | 2 |
| how | 1 |

Supporting documents/query:
| Support docs/query | Query count |
|---|---|
| 2 | 50 |

## 5. Multihop anatomy

### `5ae5669755429960a22e02ec`

> Which of the campaign that brought out the term Vichy Republican on social media was formally launched on June 16, 2015, at Trump Tower in New York City?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 49892372 |  | 42 | 0.462 | Vichy Republican is a term that emerged on social media in 2016 in regards to the United States Presidential campaign ofDonald Trump. To Trump opponents, it refers to members of th |
| 46979246 |  | 90 | 0.692 | The 2016 presidential campaign of Donald Trump, an American businessman, television personality, and author, was formally launched on June 16, 2015, at Trump Tower in New York City |

### `5a811667554299260e20a23d`

> What occupations do both Ian Hunter and Rob Thomas have?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 6668827 |  | 111 | 0.3 | Ian Hunter Patterson (born 3 June 1939), known as Ian Hunter, is a British singer-songwriter who is best known as the lead singer of the English rock band Mott the Hoople, from its |
| 580274 |  | 81 | 0.2 | Robert Kelly Thomas (born February 14, 1972) is an American singer, songwriter, record producer and multi-instrumentalist, best known as the lead singer of Alternative band Matchbo |

### `5abdf8c45542993f32c2a072`

> The Death of Cook depicts the death of James Cook at a bay on what coast?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 838269 |  | 27 | 0.583 | Death of Cook is the name of several paintings depicting the 1779 death of British and discoverer of the Hawaiian Islands, Captain James Cook at Kealakekua Bay. |
| 1214610 |  | 21 | 0.417 | Kealakekua Bay is located on the Kona coast of the island of Hawaiʻ i about 12 mi south of Kailua-Kona. |

### `5adbd70c55429947ff173843`

> What is the title of the memoir written by the honoree of the Black and White Ball?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 7727406 |  | 39 | 0.538 | The Black and White Ball was a masquerade ball held on November 28, 1966 at the Plaza Hotel in New York City. Hosted by author Truman Capote, the ball was in honor of "The Washingt |
| 408127 |  | 55 | 0.231 | Katharine Meyer Graham (June 16, 1917 – July 17, 2001) was an American publisher. She led her family's newspaper, "The Washington Post", for more than two decades, overseeing its m |

### `5ae0ae4555429945ae959419`

> Jal Pari, which translated in another language refers to which legendary creature which are sometimes associated with perilous events such as floods, storm,s shipwrecks, and drownings?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 6673260 |  | 51 | 0.12 | Jal Pari (Urdu for "Mermaid") is Atif Aslam's first solo album after he left the Pakistani rock group, Jal, released on 17 July 2004. Two of his songs from the album were used by B |
| 76592 |  | 104 | 0.64 | A mermaid is a legendary aquatic creature with the head and upper body of a female human and the tail of a fish. Mermaids appear in the folklore of many cultures worldwide, includi |

### `5a89f68f5542992e4fca84b6`

> What kind of person of authority does Governor of Sheerness and Stapleton Cotton, 1st Viscount Combermere have in common?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 29728545 |  | 105 | 0.353 | The Governor of Sheerness Fort and the Isle of Sheppey was a military officer who commanded the fortifications at Sheerness, on the Isle of Sheppey, part of the defences of the Med |
| 2399083 |  | 110 | 0.471 | Field Marshal Stapleton Cotton, 1st Viscount Combermere {'1': ", '2': ", '3': ", '4': "} (14 November 1773 – 21 February 1865), was a British Army officer, diplomat and politician. |

### `5aba67c255429955dce3ee10`

> Both The Badgeman and +44 were bands concieved in which country?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 33733292 |  | 83 | 0.455 | The Badgeman were a four-piece indie rock band from Salisbury, Wiltshire formed in 1988, although music journalist Pete Frame claims in his book "Rockin Around Britain" that the ba |
| 3785255 |  | 116 | 0.545 | +44 (read as Plus Forty-four) was an American rock supergroup formed in Los Angeles, California in 2005. The group consisted of vocalist and bassist Mark Hoppus and drummer Travis  |

### `5ab4f7fc5542991779162d43`

> Kete Krachi is a town in what region?
| doc_id | title | tokens | query overlap | preview |
|---|---|---|---|---|
| 4087014 |  | 100 | 0.875 | Kete Krachi is a town in the Krachi West District of the Volta Region of Ghana. Kete Krachi is the capital of the Krachi West District. It is in the West of the Volta region, and i |
| 4143197 |  | 26 | 0.625 | The Krachi West District is one of the twenty-five (25) districts in the Volta Region. Krachi West district capital and administrative centre is Kete Krachi. |

## 6. Vấn đề gặp trong data

| Vấn đề | Dấu hiệu trong EDA | Cách xử lý |
|---|---|---|
| Thiếu title/url ở nano | 5,090/5,090 docs có title rỗng trong sample. | Không normalize mất thông tin; khi lên full phải index và hiển thị title + text. |
| Qrels chỉ ở mức document | BEIR/nano cho query_id-doc_id; HotpotQA gốc có supporting facts mức sentence. | Metric nên thêm full_support_recall@k; nếu làm answer QA cần map lại sentence evidence. |
| Text có artifact Wikipedia | Ví dụ gặp chuỗi như 'ofDonald', khoảng trắng lạ, ký tự non-ASCII, markup còn sót. | Giữ raw text để đánh giá công bằng; tokenizer/indexer cần normalize whitespace/punctuation. |
| Query có typo/noise | Ví dụ 'concieved' trong query sample; đây là dữ liệu thật, không phải lỗi loader. | Không sửa query gốc khi evaluate; có thể dùng query expansion có guard ở baseline nâng cấp. |
| Full corpus lớn | Full BEIR có khoảng 5,233,329 docs. | Cần persistent sparse index + dense index; không load list Python cho benchmark thật. |

Các điểm trên không nên bị che đi trong presentation: đây là lý do cần metadata, preview kết quả và metric multihop thay vì chỉ báo một điểm số retrieval.

## 7. Compact vs full

| Dataset | Docs | Queries | Qrels | Document fields | Hàm ý |
|---|---|---|---|---|---|
| nano-beir/hotpotqa | 5090 | 50 | 100 | doc_id,text | không có title/url |
| beir/hotpotqa | 5233329 | 97852 | None | doc_id,title,text,url | full BEIR; cần persistent index |
| beir/hotpotqa/train | 5233329 | 85000 | 170000 | doc_id,title,text,url | full BEIR; cần persistent index |
| beir/hotpotqa/dev | 5233329 | 5447 | 10894 | doc_id,title,text,url | full BEIR; cần persistent index |
| beir/hotpotqa/test | 5233329 | 7405 | 14810 | doc_id,title,text,url | full BEIR; cần persistent index |

Khác biệt quan trọng: compact đã bỏ `title` riêng nên loader project đang đặt `title = ""`; full BEIR dùng document có `title` và `url`, vì vậy full benchmark phải index `title + text` và lưu metadata để inspect kết quả.

## 8. Paper và preprocessing

- HotpotQA gốc lưu QA examples với `_id`, `question`, `answer`, `type`, `level`, `supporting_facts`, `context`; supporting facts ở cấp title/sentence.
- Wiki preprocessing chính thức dùng dump Wikipedia đã xử lý thành page JSON có `id`, `url`, `title`, sentence text, hyperlink và char offset; đây là nguồn để map evidence về page/sentence.
- BEIR chuyển HotpotQA sang retrieval benchmark chuẩn: corpus JSONL, queries JSONL, qrels TSV; metric retrieval phổ biến là nDCG/Recall/MRR/Precision.
- MDR học dense retrieval theo chuỗi evidence: retrieve hop 1, condition hop 2 bằng evidence hop trước; phù hợp với `full_support_recall@k`.
- DrKIT đại diện hướng entity-centric: tạo virtual KB từ entity mentions/linking rồi reasoning qua entity, hữu ích cho bridge questions có entity trung gian.

Nguồn:
- [HotpotQA original paper](https://aclanthology.org/D18-1259/): Defines bridge/comparison multi-hop QA, supporting facts, and explainable QA setting.
- [HotpotQA official dataset/wiki preprocessing](https://hotpotqa.github.io/wiki-readme.html): Describes processed Wikipedia pages with title, url, sentence text, hyperlinks, and char offsets.
- [BEIR benchmark paper](https://arxiv.org/abs/2104.08663): Standardizes heterogeneous retrieval datasets including HotpotQA into corpus/query/qrels evaluation.
- [BEIR repository data format](https://github.com/beir-cellar/beir): Uses corpus.jsonl, queries.jsonl, and qrels TSV conventions for retrieval benchmarks.
- [Multi-hop Dense Retrieval](https://arxiv.org/abs/2009.12756): Retrieves evidence chains with hop-conditioned dense retrieval for open-domain multi-hop QA.
- [DrKIT](https://arxiv.org/abs/2002.10640): Shows an entity-centric differentiable retrieval/reasoning direction relevant to bridge questions.

## 9. Research pipeline từ các paper lớn

| Paper/pipeline | Họ xử lý như thế nào | Rút ra cho project này |
|---|---|---|
| [HotpotQA](https://aclanthology.org/D18-1259/) | Dataset được thiết kế cho bridge/comparison multi-hop QA và có supporting facts ở mức sentence. | Đừng chỉ show top-1 doc; phải inspect đủ evidence chain và đo đủ supporting documents. |
| [BEIR format](https://github.com/beir-cellar/beir) | Chuẩn hóa retrieval thành corpus, queries, qrels để benchmark nDCG/Recall/MRR/Precision. | Giữ pipeline tách loader/index/retriever/evaluator; qrels là contract đánh giá. |
| [GoldEn Retriever](https://arxiv.org/abs/1910.07000) | Lặp giữa đọc context đã retrieve và sinh query mới để tìm missing entity/document. | Iterative query expansion nên dựa trên evidence hop 1, không nối bừa toàn bộ top-k. |
| [Multi-hop Dense Retrieval](https://arxiv.org/abs/2009.12756) | Retrieve hop 1 rồi condition hop 2 bằng evidence đã tìm được để học evidence chain. | Dense baseline nâng cấp nên đánh giá theo chain/full_support_recall@k, không chỉ doc recall rời rạc. |
| [Baleen](https://arxiv.org/abs/2101.00436) | Condensed retrieval: sau mỗi hop tóm gọn passages đã retrieve thành context nhỏ để truy hồi tiếp. | Khi lên full corpus, phải giới hạn state giữa các hop để search space không phình theo cấp số nhân. |
| [IRCoT](https://arxiv.org/abs/2212.10509) | Interleave retrieval với từng reasoning step; step mới lại dẫn retrieval mới. | Sau baseline, có thể dùng reasoning-step/query-step làm debug view cho câu hỏi bridge khó. |
| [DrKIT](https://arxiv.org/abs/2002.10640) | Entity-centric retrieval/reasoning bằng virtual KB từ entity mentions và linking. | Bridge questions nên có entity-aware expansion hoặc entity logging để biết hop nào bị đứt. |

## 10. Framework xử lý đề xuất

| Giai đoạn | Framework | Lý do |
|---|---|---|
| Nano smoke test | Elasticsearch BM25 + BGE dense_vector | 5,090 docs nhỏ, document ngắn, chạy nhanh để debug pipeline và metric. |
| Hybrid baseline | Reciprocal Rank Fusion | Kết hợp lexical overlap cao ở hop dễ với dense semantic cho hop bridge khó. |
| Multihop baseline | iterative hybrid query expansion | Dùng top evidence hop 1 mở rộng hop 2, nhưng cần guard query drift. |
| Full benchmark | Elasticsearch persistent index | 5.23M docs không nên load list Python; cần index lưu disk, batch build, cache result. |
| Nâng cấp nghiên cứu | MDR-style retriever hoặc entity-aware expansion | Tận dụng cấu trúc evidence chain và entity trung gian của HotpotQA. |

## 11. Lệnh tái tạo

```bash
python scripts/eda_hotpotqa.py --dataset nano-beir/hotpotqa --dataset beir/hotpotqa --dataset beir/hotpotqa/train --dataset beir/hotpotqa/dev --dataset beir/hotpotqa/test --metadata-only-full --output evaluation/results/hotpotqa_eda_deep.json --markdown-output docs/data/hotpotqa_eda.md --html-output docs/data/hotpotqa_eda.html --slides-output docs/data/hotpotqa_eda_slides.html
```

