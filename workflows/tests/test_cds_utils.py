from include.utils.cds import (
    build_literature_search_url,
    build_report_search_url,
    get_record_for_provided_ids,
    has_any_id,
    search_and_return_single,
)


def test_has_any_id_without_additional_ids():
    # Only control_number present, no other IDs => should return False
    record = {"id": "2302862", "metadata": {"control_number": "2302862"}}
    assert has_any_id(record) is False


def test_has_any_id_with_any_id_present():
    # other_ids present => should return True
    record = {
        "id": "2635152",
        "metadata": {
            "control_number": "2635152",
            "other_ids": ["1674998"],
            "eprints": ["eprint1"],
            "dois": [{"value": "10.1093/mnras/stx1357"}],
            "report_numbers": [{"value": "RN123"}],
        },
    }
    assert has_any_id(record) is True


def test_build_literature_search_url_multiple_clauses():
    control_numbers = ["123", "456"]
    arxivs = ["1901.1234"]
    dois = ["10.0/xxx"]
    url = build_literature_search_url(control_numbers, arxivs, dois)
    expected = (
        "control_number:123 OR control_number:456 OR arxiv:1901.1234"
        " OR dois.value:10.0/xxx"
    )
    assert url == expected


def test_build_literature_search_url_empty():
    assert build_literature_search_url([], [], []) is None


def test_build_report_search_url_varied(monkeypatch):
    # Stub is_arxiv to recognize specific candidate
    monkeypatch.setattr("include.utils.cds.is_arxiv", lambda x: x == "1706.01046")
    report_numbers = ["arXiv:1706.01046", "RNABC"]
    url = build_report_search_url(report_numbers)
    expected = 'arxiv:1706.01046 OR report_numbers.value.fuzzy:"RNABC"'
    assert url == expected


def test_build_report_search_url_empty():
    assert build_report_search_url([]) is None


class DummyHook:
    def __init__(self, response_payload):
        self._resp = response_payload

    def search_records(self, pid_type, query_params):
        return self._resp


def testsearch_and_return_single_single_hit(tmp_path):
    # Single hit => returns its control_number
    resp = {"hits": {"hits": [{"metadata": {"control_number": 123}}]}}
    hook = DummyHook(resp)
    result = search_and_return_single(hook, "q=test", "log msg")
    assert result == 123


def testsearch_and_return_single_no_hits():
    # Zero hits => returns None
    hook = DummyHook({"hits": {"hits": []}})
    result = search_and_return_single(hook, "q=test", "log msg")
    assert result is None


def testsearch_and_return_single_multiple_hits():
    # More than one hit => returns None
    hook = DummyHook({"hits": {"hits": [{}, {}]}})
    result = search_and_return_single(hook, "q=test", "log msg")
    assert result is None


def test_get_record_for_provided_ids_prioritize_literature(monkeypatch):
    # If literature search returns a recid, it is returned first
    monkeypatch.setattr(
        "include.utils.cds.search_and_return_single",
        lambda hook, query_url, log_message: 10,
    )
    recid = get_record_for_provided_ids(
        inspire_http_record_management_hook=None,
        control_numbers=["1"],
        arxivs=[],
        dois=[],
        report_numbers=[],
    )
    assert recid == 10


def test_get_record_for_provided_ids_fallback_to_report(monkeypatch):
    # If literature search URL is None, report search is attempted
    monkeypatch.setattr(
        "include.utils.cds.search_and_return_single",
        lambda hook, query_url, log_message: 20,
    )
    recid = get_record_for_provided_ids(
        inspire_http_record_management_hook=None,
        control_numbers=[],
        arxivs=[],
        dois=[],
        report_numbers=["RN1"],
    )
    assert recid == 20


def test_get_record_for_provided_ids_none(monkeypatch):
    # Neither search yields a recid
    monkeypatch.setattr(
        "include.utils.cds.search_and_return_single",
        lambda hook, query_url, log_message: None,
    )
    recid = get_record_for_provided_ids(
        inspire_http_record_management_hook=None,
        control_numbers=[],
        arxivs=[],
        dois=[],
        report_numbers=[],
    )
    assert recid is None
