import logging

from idutils import is_arxiv
from inspire_utils.record import get_value

logger = logging.getLogger(__name__)

LITERATURE_PID_TYPE = "literature"


def has_any_id(cds_record):
    cds_id = cds_record.get("id") or get_value(
        cds_record, "metadata.control_number", []
    )
    if not cds_id:
        logger.info(f"Cannot extract CDS id from CDS response: {cds_record}")
        return False
    return any(
        [
            get_value(cds_record, "metadata.other_ids", []),
            get_value(cds_record, "metadata.eprints", []),
            get_value(cds_record, "metadata.dois.value", []),
            get_value(cds_record, "metadata.report_numbers.value", []),
        ]
    )


def search_and_return_single(
    hook,
    query_url,
    log_message,
):
    """
    Build query params from the URL, call search_records,
    and if exactly one hit is found
    return its metadata with a log; otherwise return None.
    """
    query_params = {
        "q": query_url,
        "fields": "control_number",
    }
    logger.info(
        f"Searching for record with query: {query_params}",
    )
    resp = hook.search_records(pid_type=LITERATURE_PID_TYPE, query_params=query_params)
    logger.info(
        f"Response from search: {resp}",
    )
    hits = resp.get("hits", {}).get("hits", [])
    logger.info(
        f"Found {len(hits)} hits for query",
    )
    if len(hits) == 1:
        record = hits[0]["metadata"]
        control_number = record.get("control_number")
        logger.info(f"{log_message} Control number: {control_number}")
        return control_number
    return None


def get_record_for_provided_ids(
    inspire_http_record_management_hook, control_numbers, arxivs, dois, report_numbers
):
    lit_url = build_literature_search_url(control_numbers, arxivs, dois)
    if lit_url:
        recid = search_and_return_single(
            hook=inspire_http_record_management_hook,
            query_url=lit_url,
            log_message="Matched record by `control_number`, `arxiv`, or `doi`.",
        )
        if recid:
            return recid

    rn_url = build_report_search_url(report_numbers)
    if rn_url:
        return search_and_return_single(
            hook=inspire_http_record_management_hook,
            query_url=rn_url,
            log_message="Matched record by `report_number`.",
        )
    return None


def build_literature_search_url(
    control_numbers,
    arxivs,
    dois,
):
    """
    Build an Elasticsearch‐style query URL that matches any of the provided
    control_numbers, arxivs or dois.

    e.g. q=control_number:1234 OR control_number:5678 OR arxiv:1901.1234 OR ...
    """
    clauses = []
    for cn in control_numbers:
        clauses.append(f"control_number:{cn}")
    for ax in arxivs:
        clauses.append(f"arxiv:{ax}")
    for doi in dois:
        clauses.append(f"dois.value:{doi}")

    if clauses:
        return " OR ".join(clauses)
    return None


def build_report_search_url(report_numbers):
    """
    Construct a single search URL that matches any of the provided report_numbers,
    either as an arxiv:id or as a fuzzy report_numbers.value match.
    """
    clauses = []
    for rn in report_numbers:
        candidate = rn.lower().split("arxiv:")[-1]
        if is_arxiv(candidate):
            clauses.append(f"arxiv:{candidate}")
        else:
            clauses.append(f'report_numbers.value.fuzzy:"{rn}"')
    if clauses:
        return " OR ".join(clauses)
    return None
