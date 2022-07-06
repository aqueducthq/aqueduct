from typing import List
import json
import os
import subprocess
from pathlib import Path
import argparse
from aqueduct import Client
import time

from aqueduct.error import InvalidUserArgumentException

"""
See README.md for details about this script.
"""

# These are the prefixes that we use to identify and extract client credentials from the notebook.
API_KEY_CODE_SNIPPET = "api_key = "
SERVER_ADDRESS_CODE_SNIPPET = "address = "

parser = argparse.ArgumentParser()
parser.add_argument("--path", required=True, help="The relative path to the notebook to run.")
parser.add_argument(
    "--flow_id",
    required=False,
    default=None,
    help="The flow id that the notebook publishes. If not supplied, we will attempt to infer from the code.",
)
parser.add_argument(
    "--api_key",
    required=False,
    default=None,
    help="The api_key to use when running the notebook, instead of the notebook value.",
)
parser.add_argument(
    "--server_address",
    required=False,
    default=None,
    help="The server address to use when running the notebook, instead of the notebook value.",
)
args = parser.parse_args()


def infer_flow_ids_from_stdout(
    client: Client, code_block_list: List[str], stdout: str
) -> List[str]:
    """
    If you have a notebook that is publishing a workflow, but you don't know the flow id of the flow beforehand,
    or you know and don't want to hard code it in some automated system, this method will attempt to figure out
    the published flow by looking at the notebook's standard output.

    The means that you must print the id of the published workflow in the notebook. Otherwise, this method will
    complain.
    """
    import re

    UUID_REGEX = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    CELL_HEADER_OUTPUT_TEMPLATE = "Cell %d"
    PUBLISH_CODE_SNIPPET = ".publish_flow("

    cell_num_to_publish_freq = {
        i: code_block.count(PUBLISH_CODE_SNIPPET) for i, code_block in enumerate(code_block_list)
    }
    # For convenience, lets just restrict to one publish max per cell.
    if any(count > 1 for count in cell_num_to_publish_freq.values()):
        raise Exception("Multiple publish_flow() calls in the same cell. Can we split them up?")

    cells_that_publish = sorted([i for i, count in cell_num_to_publish_freq.items() if count > 0])

    print(
        "There are flows that have been published by this notebook in cells: %s"
        % ", ".join([str(x) for x in cells_that_publish])
    )

    flow_ids = []
    for cell_num in cells_that_publish:
        start_idx = stdout.find(CELL_HEADER_OUTPUT_TEMPLATE % cell_num)
        end_idx = stdout.find(CELL_HEADER_OUTPUT_TEMPLATE % (cell_num + 1))
        if end_idx < 0:
            end_idx = len(stdout)

        # Isolate the output of the cell and extract any printed UUIDs.
        cell_output = stdout[start_idx:end_idx]
        candidate_flow_ids = re.findall(UUID_REGEX, cell_output)
        if len(candidate_flow_ids) == 0:
            raise Exception(
                "Cell %d had a publish_flow() call but did not print out out uuid." % cell_num
            )
        print(
            "Found uuids %s in output of cell number %d. Checking that at least one corresponds to a flow. \n"
            % (", ".join(candidate_flow_ids), cell_num)
        )

        # Check if any of these ids correspond to existing flows.
        validated_flow_ids = []
        for candidate_flow_id in candidate_flow_ids:
            try:
                _ = client.flow(candidate_flow_id)
            except InvalidUserArgumentException:
                pass
            else:
                print("Flow %s corresponds to an actual workflow." % candidate_flow_id)
                validated_flow_ids.append(candidate_flow_id)

        if len(validated_flow_ids) == 0:
            raise Exception(
                "Cell %d had a publish_flow() call but did not print any valid flow ids for us to track."
                % cell_num
            )
        flow_ids.extend(validated_flow_ids)

    # Deduplicate before returning
    return list(set(flow_ids))

# The name of the python script to create from the notebook. This will be deleted after the notebook runs.
NOTEBOOK_SCRIPT_NAME = "temp.py"
CELL_CODE_HEADER_TEMPLATE = 'print("Cell %d")\n'

notebook_path = Path(args.path)
notebook_dir = os.path.dirname(notebook_path.as_posix())
notebook_script_path = os.path.join(notebook_dir, NOTEBOOK_SCRIPT_NAME)

with open(notebook_path, "r") as f:
    notebook = json.load(f)

# Pull out the notebook code.
code_blocks = [c["source"] for c in notebook["cells"] if c["cell_type"] == "code"]
code_block_list = [
    "".join([CELL_CODE_HEADER_TEMPLATE % i] + block) for i, block in enumerate(code_blocks)
]

code = "\n\n\n".join(code_block_list)


# Pull out the client credential value in the notebook, formatted like "<credential_prefix> <value>\n".
# Strips out any quotes.
def extract_credential(credential_prefix: str) -> str:
    start_idx = code.find(credential_prefix)
    if start_idx < 0:
        raise Exception("Unable to find expected pattern `%s` in notebook.", credential_prefix)
    end_idx = code.find("\n", start_idx)
    return code[start_idx + len(credential_prefix) : end_idx].strip('"')


# Fetch the client credentials from within the notebook in order to instantiate the same client in this script.
# Overwrite the api_key value if supplied as a command line argument.
api_key = extract_credential(API_KEY_CODE_SNIPPET)
if args.api_key is not None:
    new_api_key = args.api_key.strip('"')
    code = code.replace(api_key, new_api_key)
    api_key = new_api_key

server_address = extract_credential(SERVER_ADDRESS_CODE_SNIPPET)
if args.server_address is not None:
    new_server_address = args.server_address.strip('"')
    code = code.replace(server_address, new_server_address)
    server_address = new_server_address

with open(notebook_script_path, "w") as f:
    f.write(code)

start_time = time.time()
process = subprocess.Popen(
    "cd %s && python3 %s" % (notebook_dir, NOTEBOOK_SCRIPT_NAME),
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
stdout_raw, stderr_raw = process.communicate()
stdout = stdout_raw.decode("utf-8")
stderr = stderr_raw.decode("utf-8")
print("========= STDOUT ==========")
print(stdout)
print("========= STDERR ==========")
print(stderr)

# Remove the generated python script.
os.remove(notebook_script_path)

if process.returncode:
    raise Exception("Notebook did not execute correctly!")

print("Notebook ran successfully!\n")


# Track the flows that were published by the workflow.
# They must have at least one successful run since we executed the notebook.
client = Client(api_key, server_address)
if args.flow_id is None:
    flow_ids = infer_flow_ids_from_stdout(client, code_block_list, stdout)
else:
    flow_ids = [args.flow_id]

flowIds = ", ".join(flow_ids)
os.environ["FLOWIDS"] = flowIds

print(
    "Check that the output flow ids %s have had at least one successful run.\n"
    % ", ".join(flow_ids)
)

TIMEOUT_SECS = 60 * 10
POLL_INTERVAL_SECS = 5
begin = time.time()
while True:
    assert time.time() - begin < TIMEOUT_SECS

    time.sleep(POLL_INTERVAL_SECS)

    successful_flow_ids = set([])
    for flow_id in flow_ids:
        if flow_id in successful_flow_ids:
            continue

        flow = client.flow(str(flow_id))

        # A flow has been successfully published if it makes at least one successful workflow run since start_time,
        flow_runs = [flow.fetch(flow_run_dict["run_id"]) for flow_run_dict in flow.list_runs()]
        flow_runs = [flow_run for flow_run in flow_runs if float(flow_run._created_at) > start_time]
        if len(flow_runs) == 0:
            continue

        assert all(
            flow_run.status() != "failed" for flow_run in flow_runs
        ), "At least one workflow run failed!"

        # Continue checking as long as there are still runs pending.
        if any(flow_run.status() == "pending" for flow_run in flow_runs):
            continue

        print("Flow %s has completed a full run!" % flow_id)
        successful_flow_ids.add(flow_id)

    if len(successful_flow_ids) >= len(flow_ids):
        break

print("All flows have run successfully! Exiting script...")
