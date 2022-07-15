#!/bin/bash
JOB_SPEC=$1
OP_PATH=$(python3 -m aqueduct_executor.operators.function_executor.get_extract_path --spec "$JOB_SPEC")
EXIT_CODE=$?
if [ $EXIT_CODE != "0" ]; then exit $(($EXIT_CODE)); fi

python3 -m aqueduct_executor.operators.function_executor.extract_function --spec "$JOB_SPEC"
EXIT_CODE=$?
if [ $EXIT_CODE != "0" ]; then exit $(($EXIT_CODE)); fi

if test -f "$OP_PATH/requirements.txt"; then pip3 install -r "$OP_PATH/requirements.txt" --no-cache-dir; fi

python3 -m aqueduct_executor.operators.function_executor.main --spec "$JOB_SPEC"
EXIT_CODE=$?

# Remove the /op suffix.
FUNCTION_EXTRACT_PATH=${OP_PATH::-3}
# Double check to make sure the path doesn't contain something dangerous.
if [ ! -z "$FUNCTION_EXTRACT_PATH" -a "$FUNCTION_EXTRACT_PATH" != *"*"* ]
then
      rm -rf $FUNCTION_EXTRACT_PATH
fi

# Exit after cleanup, regardless of execution success / failure.
exit $(($EXIT_CODE))