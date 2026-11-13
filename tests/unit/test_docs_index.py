from project_docs_agent import docs_index
from project_docs_agent.agent import list_docs, read_doc_section, search_docs


def test_docs_are_bundled() -> None:
    docs = {s.doc for s in docs_index.sections()}
    assert {"architecture.md", "operations.md", "history.md"} <= docs


def test_search_finds_agent_identity_section() -> None:
    result = search_docs("switch runtime to Agent Identity")
    assert result["status"] == "success"
    assert any("Agent Identity" in r["heading"] for r in result["results"])


def test_search_with_only_stopwords_returns_no_results() -> None:
    assert search_docs("how do the")["status"] == "no_results"


def test_read_doc_section_round_trip() -> None:
    first = docs_index.sections()[0]
    result = read_doc_section(first.doc, first.heading)
    assert result["status"] == "success"
    assert read_doc_section("missing.md", "x")["status"] == "not_found"


def test_list_docs() -> None:
    assert list_docs()["status"] == "success"
