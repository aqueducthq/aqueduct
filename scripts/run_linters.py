"""
Lints the code for various components. Run with `python3 scripts/run_linters.py` from the root directory of the aqueduct repo.

Requirements:
- For the Python code linting, please install the following:
`pip3 install --upgrade black mypy pydantic types-croniter types-requests types-PyYAML`
- For the Golang linter, please install `golangci-lint` following the instruction here: https://golangci-lint.run/usage/install/
- For the UI linter, please install node with the version suggested by running `nvm use` from `src/ui`.

If you don't specify any component flag, the script will lint all components. Keep in mind that UI
takes longer to lint.
"""

import argparse
import os
import subprocess
import sys

from os.path import join


def execute_command(args, cwd=None):
    with subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd) as proc:
        proc.communicate()
        if proc.returncode != 0:
            raise Exception("Error executing command: %s" % args)

def lint_python(cwd):
    execute_command(["black", join(cwd, "src/python"), "--line-length=100"])
    execute_command(["black", join(cwd, "sdk"), "--line-length=100"])
    execute_command(["black", join(cwd, "integration_tests"), "--line-length=100"])
    execute_command(["mypy", ".", "--ignore-missing-imports", "--strict", "--exclude", "aqueduct/tests", "--implicit-reexport"], join(cwd, "sdk"))
    execute_command(["mypy", ".", "--ignore-missing-imports", "--strict", "--exclude", "tests", "--implicit-reexport"], join(cwd, "src/python"))

def lint_golang(cwd):
    execute_command(["golangci-lint", "run", "--concurrency=4", "--fix"], join(cwd, "src/golang"))

def lint_ui(cwd):
    execute_command(["npm", "install"], join(cwd, "src/ui/common"))
    execute_command(["npm", "run", "lint", "--", "--fix"], join(cwd, "src/ui/common"))
    execute_command(["npm", "link"], join(cwd, "src/ui/common"))
    execute_command(["npm", "link", "@aqueducthq/common"], join(cwd, "src/ui/app"))
    execute_command(["npm", "run", "lint", "--", "--fix"], join(cwd, "src/ui/app"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--lint-python",
        dest="lint_python",
        default=False,
        action="store_true",
        help="Whether to lint all Python code.",
    )

    parser.add_argument(
        "--lint-golang",
        dest="lint_golang",
        default=False,
        action="store_true",
        help="Whether to lint all Go code.",
    )

    parser.add_argument(
        "--lint-ui",
        dest="lint_ui",
        default=False,
        action="store_true",
        help="Whether to lint all UI code.",
    )

    args = parser.parse_args()

    if not (args.lint_python or args.lint_golang or args.lint_ui):
        args.lint_python = True
        args.lint_golang = True
        args.lint_ui = True

    cwd = os.getcwd()
    if not cwd.endswith("aqueduct"):
        print("Current directory should be the root directory of the aqueduct repo.")
        print("Your working directory is %s" % cwd)
        exit(1)

    if args.lint_python:
        print("Linting Python code...")
        lint_python(cwd)

    if args.lint_golang:
        print("Linting Go code...")
        lint_golang(cwd)

    if args.lint_ui:
        print("Linting UI code...")
        lint_ui(cwd)