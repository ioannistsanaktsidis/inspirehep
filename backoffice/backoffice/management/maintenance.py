"""Ad-hoc maintenance helpers meant to be run from `python manage.py shell`.

Example:
    >>> from backoffice.management.maintenance import restart_stuck_workflows
    >>> restart_stuck_workflows()
    >>> restart_stuck_workflows(
    ...     stuck_hep_statuses=[HepStatusChoices.ERROR],
    ...     workflow_types=[HepWorkflowType.HEP_CREATE, HepWorkflowType.HEP_UPDATE],
    ... )
    >>> from backoffice.management.maintenance import trigger_missing_workflows
    >>> trigger_missing_workflows()
    >>> trigger_missing_workflows(
    ...     statuses=[HepStatusChoices.PROCESSING],
    ...     workflow_types=[HepWorkflowType.HEP_CREATE],
    ... )
"""

import logging
import time

from requests.exceptions import RequestException

from backoffice.authors.api.serializers import AuthorWorkflowSerializer
from backoffice.authors.constants import AuthorStatusChoices, AuthorWorkflowType
from backoffice.authors.models import AuthorWorkflow
from backoffice.common.airflow_utils import clear_airflow_dag_run, trigger_airflow_dag
from backoffice.common.constants import WORKFLOW_DAGS
from backoffice.hep.constants import HepStatusChoices, HepWorkflowType
from backoffice.hep.models import HepWorkflow

logger = logging.getLogger(__name__)

STUCK_HEP_STATUSES = [HepStatusChoices.ERROR]
WORKFLOW_TYPES = [HepWorkflowType.HEP_CREATE]

# workflow type -> (model, serializer used to build the dag conf)
WORKFLOW_MODELS = {
    HepWorkflowType.HEP_CREATE: (HepWorkflow, None),
    HepWorkflowType.HEP_PUBLISHER_CREATE: (HepWorkflow, None),
    HepWorkflowType.HEP_PUBLISHER_UPDATE: (HepWorkflow, None),
    HepWorkflowType.HEP_SUBMISSION: (HepWorkflow, None),
    HepWorkflowType.HEP_UPDATE: (HepWorkflow, None),
    AuthorWorkflowType.AUTHOR_CREATE: (AuthorWorkflow, AuthorWorkflowSerializer),
    AuthorWorkflowType.AUTHOR_UPDATE: (AuthorWorkflow, AuthorWorkflowSerializer),
}

MISSING_WORKFLOW_TYPES = [
    HepWorkflowType.HEP_CREATE,
    HepWorkflowType.HEP_PUBLISHER_CREATE,
    HepWorkflowType.HEP_PUBLISHER_UPDATE,
    HepWorkflowType.HEP_SUBMISSION,
    HepWorkflowType.HEP_UPDATE,
]

# a workflow whose dag was never created never leaves its initial status
NOT_STARTED_STATUSES = {
    HepWorkflow: [HepStatusChoices.PROCESSING, HepStatusChoices.RUNNING],
    AuthorWorkflow: [AuthorStatusChoices.PROCESSING, AuthorStatusChoices.RUNNING],
}


def restart_stuck_workflows(
    stuck_hep_statuses=None,
    workflow_types=None,
    batch_size=30,
    sleep_between_batches=10,
    only_failed=True,
):
    """Restart stuck HEP workflows by clearing their initialize DAG run.

    :param stuck_hep_statuses: statuses to pick up (defaults to STUCK_HEP_STATUSES)
    :param workflow_types: workflow types to restart (defaults to WORKFLOW_TYPES)
    :param batch_size: how many workflows to restart before sleeping
    :param sleep_between_batches: seconds to sleep between batches
    :param only_failed: restart only the failed/current task instead of from scratch
    """
    stuck_hep_statuses = stuck_hep_statuses or STUCK_HEP_STATUSES
    workflow_types = workflow_types or WORKFLOW_TYPES

    statuses = [str(status) for status in stuck_hep_statuses]
    types = [str(workflow_type) for workflow_type in workflow_types]

    logger.info(
        "Restarting stuck workflows: statuses=%s types=%s "
        "batch_size=%s sleep=%ss only_failed=%s",
        statuses,
        types,
        batch_size,
        sleep_between_batches,
        only_failed,
    )

    failed = []
    for workflow_type in types:
        workflows = HepWorkflow.objects.filter(
            status__in=statuses, workflow_type=workflow_type
        ).order_by("id")

        total = workflows.count()
        logger.info("Found %s stuck workflow(s) of type %s", total, workflow_type)

        for index, workflow in enumerate(workflows.iterator(), start=1):
            dag_id = WORKFLOW_DAGS[workflow.workflow_type].initialize
            logger.info("Restarting workflow %s (dag=%s)", workflow.id, dag_id)
            try:
                clear_airflow_dag_run(dag_id, str(workflow.id), only_failed=only_failed)
            except RequestException:
                logger.exception("Failed to restart workflow %s", workflow.id)
                failed.append(workflow.id)
                continue

            if index % batch_size == 0:
                logger.info(
                    "Restarted %s workflow(s), sleeping %ss",
                    index,
                    sleep_between_batches,
                )
                time.sleep(sleep_between_batches)

    if failed:
        logger.info("Failed to restart %s workflow(s): %s", len(failed), failed)
    else:
        logger.info("All stuck workflows restarted successfully.")

    return failed


def trigger_missing_workflows(
    workflow_types=None,
    statuses=None,
    batch_size=30,
    sleep_between_batches=10,
):
    """Trigger the initialize DAG for workflows that were never created in Airflow.

    Workflows that already have a dag run make Airflow answer 409, they are
    logged and reported as failed.

    :param workflow_types: workflow types to trigger (defaults to MISSING_WORKFLOW_TYPES).
        HEP_MANUAL_MERGE is not supported, its dag conf cannot be rebuilt from
        the workflow alone
    :param statuses: statuses to pick up, defaults to the statuses a workflow whose
        dag was never created stays in (see NOT_STARTED_STATUSES)
    :param batch_size: how many workflows to trigger before sleeping
    :param sleep_between_batches: seconds to sleep between batches
    :returns: list of workflow ids that could not be triggered
    """
    workflow_types = workflow_types or MISSING_WORKFLOW_TYPES

    unsupported = [
        str(workflow_type)
        for workflow_type in workflow_types
        if workflow_type not in WORKFLOW_MODELS
    ]
    if unsupported:
        raise ValueError(f"Unsupported workflow type(s): {unsupported}")

    logger.info(
        "Triggering missing workflows: types=%s statuses=%s batch_size=%s sleep=%ss",
        [str(workflow_type) for workflow_type in workflow_types],
        statuses and [str(status) for status in statuses],
        batch_size,
        sleep_between_batches,
    )

    failed = []
    for workflow_type in workflow_types:
        model, serializer_class = WORKFLOW_MODELS[workflow_type]
        dag_id = WORKFLOW_DAGS[workflow_type].initialize

        workflow_statuses = statuses or NOT_STARTED_STATUSES[model]
        workflows = model.objects.filter(
            workflow_type=str(workflow_type),
            status__in=[str(status) for status in workflow_statuses],
        ).order_by("_created_at")

        total = workflows.count()
        logger.info("Found %s workflow(s) of type %s", total, workflow_type)

        for index, workflow in enumerate(workflows.iterator(), start=1):
            logger.info("Triggering workflow %s (dag=%s)", workflow.id, dag_id)

            trigger_kwargs = {}
            if serializer_class:
                trigger_kwargs["workflow"] = serializer_class(workflow).data

            try:
                trigger_airflow_dag(dag_id, str(workflow.id), **trigger_kwargs)
            except RequestException:
                logger.exception("Failed to trigger workflow %s", workflow.id)
                failed.append(workflow.id)
                continue

            if index % batch_size == 0:
                logger.info(
                    "Triggered %s workflow(s), sleeping %ss",
                    index,
                    sleep_between_batches,
                )
                time.sleep(sleep_between_batches)

    if failed:
        logger.info("Failed to trigger %s workflow(s): %s", len(failed), failed)
    else:
        logger.info("All missing workflows triggered successfully.")

    return failed
