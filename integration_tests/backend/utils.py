import time
import uuid
from typing import Optional

from aqueduct.enums import ExecutionStatus

import aqueduct


def wait_for_flow_runs(
    client: aqueduct.Client, flow_id: str, num_runs: int = 1, expect_success: Optional[bool] = None
) -> int:
    """
    Returns only when the specified flow has run successfully at least `num_runs` times.
    Any run failure is not tolerated. Will timeout after a few minutes.

    Returns:
        The number of successful runs this flow has performed.
    """
    timeout = 300
    poll_threshold = 5
    begin = time.time()

    while True:
        assert time.time() - begin < timeout, "Timed out waiting for workflow run to complete."

        time.sleep(poll_threshold)

        # A flow has been successfully published if it makes at least one workflow run, and
        # all its workflow runs have executed successfully.
        flow = client.flow(flow_id)
        flow_runs = flow.list_runs()
        if len(flow_runs) == 0:
            continue

        statuses = [flow_run["status"] for flow_run in flow_runs]

        # Continue checking as long as there are still runs pending.
        if any(status == ExecutionStatus.PENDING for status in statuses):
            continue

        if len(flow_runs) < num_runs:
            continue

        if expect_success is not None:
            if expect_success:
                assert all(
                    status == ExecutionStatus.SUCCEEDED for status in statuses
                ), "At least one workflow run failed!"
            else:
                # We expect them all to fail.
                assert all(
                    status == ExecutionStatus.FAILED for status in statuses
                ), "At least one workflow succeeded!"

        print(
            "Workflow %s was created and ran successfully at least %s times!"
            % (flow_id, len(flow_runs))
        )
        return len(flow_runs)
    return -1


def delete_flow(client: aqueduct.Client, workflow_id: str) -> None:
    try:
        client.delete_flow(workflow_id)
    except Exception as e:
        print("Error deleting workflow %s with exception %s" % (workflow_id, e))
    else:
        print("Successfully deleted workflow %s" % (workflow_id))
