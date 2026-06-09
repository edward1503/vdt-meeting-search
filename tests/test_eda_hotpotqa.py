from __future__ import annotations

from collections import namedtuple

from scripts import eda_hotpotqa


def test_schema_for_record_reports_namedtuple_fields_and_values():
    doc_type = namedtuple("GenericDoc", ["doc_id", "text"])
    schema = eda_hotpotqa.schema_for_record(doc_type("974", "Ada Lovelace was a mathematician."))

    assert schema["type"] == "GenericDoc"
    assert schema["fields"] == ["doc_id", "text"]
    assert schema["values"]["doc_id"] == "974"
    assert "Ada Lovelace" in schema["values"]["text"]


def test_build_support_examples_joins_query_qrels_and_documents():
    query_type = namedtuple("GenericQuery", ["query_id", "text"])
    qrel_type = namedtuple("TrecQrel", ["query_id", "doc_id", "relevance", "iteration"])
    doc_type = namedtuple("GenericDoc", ["doc_id", "text"])

    examples = eda_hotpotqa.build_support_examples(
        queries=[query_type("q1", "What connects Alpha and Beta?")],
        qrels=[qrel_type("q1", "d1", 1, "0"), qrel_type("q1", "d2", 1, "0")],
        docs_by_id={
            "d1": doc_type("d1", "Alpha mentions a bridge entity."),
            "d2": doc_type("d2", "Beta resolves the final answer."),
        },
        max_examples=1,
    )

    assert examples == [
        {
            "query_id": "q1",
            "query": "What connects Alpha and Beta?",
            "support_doc_count": 2,
            "support_docs": [
                {
                    "doc_id": "d1",
                    "title": "",
                    "text_preview": "Alpha mentions a bridge entity.",
                    "text_tokens": 5,
                    "query_token_overlap": 0.2,
                },
                {
                    "doc_id": "d2",
                    "title": "",
                    "text_preview": "Beta resolves the final answer.",
                    "text_tokens": 5,
                    "query_token_overlap": 0.2,
                },
            ],
        }
    ]


def test_markdown_and_html_reports_include_required_decision_sections():
    payload = {
        "reports": [
            {
                "dataset_id": "nano-beir/hotpotqa",
                "metadata": {"docs_count": 2, "queries_count": 1, "qrels_count": 2},
                "schema": {"document": {"type": "GenericDoc", "fields": ["doc_id", "text"]}},
                "support_examples": [],
            }
        ]
    }

    markdown = eda_hotpotqa.render_markdown_report(payload)
    html = eda_hotpotqa.render_html_report(payload)

    for required in [
        "Cấu trúc dữ liệu",
        "Preview vài dòng data",
        "Vấn đề gặp trong data",
        "Compact vs full",
        "Paper và preprocessing",
        "Research pipeline từ các paper lớn",
        "Framework xử lý đề xuất",
    ]:
        assert required in markdown
        assert required in html

def test_html_report_renders_markdown_tables_as_html_tables():
    payload = {"reports": [{"dataset_id": "nano-beir/hotpotqa", "metadata": {"docs_count": 2, "queries_count": 1, "qrels_count": 2}}]}

    html = eda_hotpotqa.render_html_report(payload)

    assert "<table>" in html
    assert "<pre class='table'>" not in html


def test_slide_deck_html_presents_eda_as_multiple_readable_pages():
    payload = {
        "reports": [
            {"dataset_id": "nano-beir/hotpotqa", "metadata": {"docs_count": 5090, "queries_count": 50, "qrels_count": 100}, "support_examples": [{"query": "Which campaign launched at Trump Tower?", "support_docs": [{"doc_id": "d1", "text_preview": "Term emerged on social media.", "text_tokens": 42, "query_token_overlap": 0.462}, {"doc_id": "d2", "text_preview": "Campaign launched on June 16, 2015 at Trump Tower.", "text_tokens": 90, "query_token_overlap": 0.692}]}]},
            {"dataset_id": "beir/hotpotqa/dev", "metadata": {"docs_count": 5233329, "queries_count": 5447, "qrels_count": 10894}},
        ]
    }

    deck = eda_hotpotqa.render_slide_deck_html(payload)

    assert deck.count("<section") >= 10
    for required in [
        "Dữ liệu",
        "Preview vài dòng data",
        "Vấn đề",
        "Research pipeline",
        "Hướng xử lý",
        "5,090",
        "5,233,329",
        "full_support_recall@k",
        "GoldEn Retriever",
        "IRCoT",
    ]:
        assert required in deck
    assert "window.location.hash" in deck
