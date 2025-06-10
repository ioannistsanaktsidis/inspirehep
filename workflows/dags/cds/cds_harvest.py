import datetime
import logging

from airflow.decorators import dag, task
from airflow.models.param import Param
from hooks.generic_http_hook import GenericHttpHook
from hooks.inspirehep.inspire_http_record_management_hook import (
    InspireHTTPRecordManagementHook,
)
from include.utils.alerts import task_failure_alert
from include.utils.cds import get_record_for_provided_ids, has_any_id
from include.utils.constants import LITERATURE_PID_TYPE
from inspire_utils.record import get_value, get_values_for_schema

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


@dag(
    start_date=datetime.datetime(2025, 5, 22),
    schedule="@daily",
    catchup=False,
    tags=["cds"],
    params={
        "since": Param(type=["null", "string"], default=""),
    },
    on_failure_callback=task_failure_alert,
)
def cds_harvest_dag():
    """DAG for harvesting CDS and updating Inspire in batches."""
    generic_http_hook = GenericHttpHook(http_conn_id="cds_connection")

    @task(task_id="get_cds_data")
    def get_cds_data(**context) -> list[dict]:
        since = context["params"]["since"] or context["ds"]
        logger.info(f"Harvesting CDS data since {since}")
        cds_response = generic_http_hook.call_api(
            endpoint="/api/inspire2cdsids", method="GET", params={"since": since}
        )
        cds_response.raise_for_status()

        hits = cds_response.json().get("hits", [])
        logger.info(f"CDS response: {len(hits)} total hits")
        filtered_hits = [hit for hit in hits if has_any_id(hit)]
        logger.info(
            f"Filtered CDS response: {len(filtered_hits)} hits with at least one ID"
        )
        return filtered_hits

    @task(task_id="chunk_records")
    def chunk_records(all_records: list[dict]) -> list[list[dict]]:
        chunks: list[list[dict]] = []
        for i in range(0, len(all_records), BATCH_SIZE):
            batch = all_records[i : i + BATCH_SIZE]
            chunks.append(batch)
        logger.info(
            f"Split {len(all_records)} records into {len(chunks)}"
            f"batches (size {BATCH_SIZE})."
        )
        return chunks

    @task.virtualenv(
        requirements=["inspire-schemas>=61.6.17"],
        system_site_packages=False,
        task_id="process_cds_batch",
    )
    def process_cds_batch(batch_of_hits: list[dict]):
        import logging

        from inspire_schemas.builders import LiteratureBuilder

        logger = logging.getLogger(__name__)

        inspire_hook = InspireHTTPRecordManagementHook()

        for cds_record in batch_of_hits:
            # 1) gather all possible IDs from the CDS payload
            control_numbers = get_value(cds_record, "metadata.other_ids", [])
            arxivs = get_value(cds_record, "metadata.eprints", [])
            dois = get_value(cds_record, "metadata.dois.value", [])
            report_numbers = get_value(cds_record, "metadata.report_numbers.value", [])
            cds_id = cds_record.get("id") or get_value(
                cds_record, "metadata.control_number", []
            )

            # 2) find an Inspire record with any of those IDs
            try:
                record_id = get_record_for_provided_ids(
                    inspire_hook,
                    control_numbers,
                    arxivs,
                    dois,
                    report_numbers,
                )
            except Exception as e:
                logger.warning(
                    f"Error looking up Inspire record for CDS hit {cds_id}: {e}"
                )
                continue

            # If no matching Inspire record, skip
            if not record_id:
                logger.info(f"Skipping CDS hit {cds_id}: no Inspire record found.")
                continue

            # 3) Attempt to fetch the Inspire record
            try:
                record = inspire_hook.get_record(
                    pid_type=LITERATURE_PID_TYPE, control_number=record_id
                )
            except Exception:
                logger.info(
                    f"Skipping CDS hit {cds_id}: "
                    f"error fetching Inspire record {record_id}."
                )
                continue

            record_metadata = record.get("metadata", {})
            # 4) Check if CDS ID is already present
            existing_ids = record_metadata.get("external_system_identifiers", [])
            cds_values = get_values_for_schema(existing_ids, "CDS")
            if cds_id in cds_values:
                logger.info(
                    f"Skipping CDS hit {cds_id}: already in "
                    f"Inspire record {record_metadata.get('control_number')}"
                )
                continue

            # 5) Build a new record payload with LiteratureBuilder
            revision = record_metadata.get("revision_id", 0)
            builder = LiteratureBuilder(record=record_metadata)
            builder.add_external_system_identifier(cds_id, "CDS")
            updated_payload = dict(builder.record)

            # 6) Push the update back to Inspire
            try:
                api_resp = inspire_hook.update_record(
                    data=updated_payload,
                    pid_type=LITERATURE_PID_TYPE,
                    control_number=updated_payload.get("control_number"),
                    revision_id=revision + 1,
                )
                api_resp.raise_for_status()
                logger.info(
                    f"Updated Inspire record"
                    f"{updated_payload.get('control_number')} "
                    f"with CDS ID {cds_id}"
                )
            except Exception:
                logger.error(
                    f"Failed to update Inspire record "
                    f"{updated_payload.get('control_number')}"
                    f"with CDS ID {cds_id}."
                )
                continue

    hits = get_cds_data()
    batches = chunk_records(hits)
    process_cds_batch.expand(batch_of_hits=batches)


cds_harvest_dag()
