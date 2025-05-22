import pytest
from airflow.models import DagBag
from freezegun import freeze_time

dagbag = DagBag()


@freeze_time("2024-12-11")
class TestCDSHarvest:
    dag = dagbag.get_dag("cds_harvest_dag")

    @pytest.mark.vcr
    def test_get_cds_data_vcr(self):
        task = self.dag.get_task("get_cds_data")
        res = task.execute(
            context={"ds": "2025-05-23", "params": {"since": "2025-05-23"}}
        )
        # initial value 355, filtered to 109
        assert len(res) == 109
