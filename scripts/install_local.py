"""
Installs aqueduct from the local repo. Run with `python3 scripts/install_local.py`.

Requirements:
- `aqueduct-ml` must already be installed.
- `aqueduct start` must have been run at least once since the last `aqueduct clear`. (~/.aqueduct/server must exist)
- The aqueduct server must not be running.

After this script completes, running `aqueduct start` will start the backend with the local changes.
The sdk will also be updated with any local changes.
"""

import argparse
import os
import shutil
import subprocess
import sys

from os import listdir
from os.path import isfile, join, isdir

base_directory = join(os.environ["HOME"], ".aqueduct")
server_directory = join(os.environ["HOME"], ".aqueduct", "server")
ui_directory = join(os.environ["HOME"], ".aqueduct", "ui")

# Make sure to update this if there is any schema change we want to include in the upgrade.
SCHEMA_VERSION = "10"


def execute_command(args, cwd=None):
    with subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd) as proc:
        proc.communicate()
        if proc.returncode != 0:
            raise Exception("Error executing command: %s" % args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-ui",
        dest="update_ui",
        default=False,
        action="store_true",
        help="Whether to build and replace UI files.",
    )
    args = parser.parse_args()
    print("Current directory should be the root directory of the aqueduct repo.")
    cwd = os.getcwd()
    if not cwd.endswith("aqueduct"):
        print("Your working directory is %s" % cwd)
        exit(1)

    if not isdir(server_directory):
        print("~/.aqueduct/server must exist.")
        exit(1)

    # Build and replace backend binaries.
    execute_command(["make", "server"], cwd=join(cwd, "src"))
    execute_command(["make", "executor"], cwd=join(cwd, "src"))
    execute_command(["make", "migrator"], cwd=join(cwd, "src"))
    if isfile(join(server_directory, "bin/server")):
        execute_command(["rm", join(server_directory, "bin/server")])
    if isfile(join(server_directory, "bin/executor")):
        execute_command(["rm", join(server_directory, "bin/executor")])
    if isfile(join(server_directory, "bin/migrator")):
        execute_command(["rm", join(server_directory, "bin/migrator")])

    execute_command(["cp", "./src/build/server", join(server_directory, "bin/server")])
    execute_command(["cp", "./src/build/executor", join(server_directory, "bin/executor")])
    execute_command(["cp", "./src/build/migrator", join(server_directory, "bin/migrator")])

    # Run the migrator to update to the latest schema
    execute_command([join(server_directory, "bin/migrator"), "--type", "sqlite", "goto", SCHEMA_VERSION])

    # Build and replace UI files.
    if args.update_ui:
        execute_command(["npm", "install"], cwd=join(cwd, "src/ui/common"))
        execute_command(["npm", "run", "build"], cwd=join(cwd, "src/ui/common"))
        execute_command(["sudo", "npm", "link"], cwd=join(cwd, "src/ui/common"))
        execute_command(["npm", "install"], cwd=join(cwd, "src/ui/app"))
        execute_command(["npm", "link", "@aqueducthq/common"], cwd=join(cwd, "src/ui/app"))
        execute_command(["make", "dist"], cwd=join(cwd, "src/ui"))

        files = [f for f in listdir(ui_directory) if isfile(join(ui_directory, f))]
        for f in files:
            if not f == "__version__":
                execute_command(["rm", f], cwd=ui_directory)

        shutil.copytree(join(cwd, "src/ui/app/dist"), ui_directory, dirs_exist_ok=True)

    # Install the local SDK.
    os.environ["PWD"] = join(os.environ["PWD"], "sdk")
    execute_command(["pip", "install", "."], cwd=join(cwd, "sdk"))

    # Install the local python operators.
    os.environ["PWD"] = join(os.environ["PWD"], "../src/python")
    execute_command(["pip", "install", "."], cwd=join(cwd, "src", "python"))

    print("Successfully installed aqueduct from local repo!")
