# Backend Integration Tests

These tests are run against the Aqueduct backend to check the endpoints' reads and outputs are as expected.

The `setup_class` sets up all the workflows which are read by each test. When all the tests in the suite are done, the workflows set up in `setup_class` are deleted in the `teardown_class`.

## Creating Tests
The workflows ran in setup tests are all the Python files in the `setup/` folder. Each Python file is called in the format `{python_file} {api_key} {server_address}`. At the top, you can parse those arguments like so:
```
import sys
api_key, server_address = sys.argv[1], sys.argv[2]
```
After that, you can write a workflow as you would do as a typical user.
At the very end, the tests **require** you to print the flow id and number of flow runs(e.g. `print(flow.id(), n_runs)`). This is parsed by the suite setup function and saved to a list of flow ids. At the end of testing, the teardown function will iterate through the flow ids and delete the associated workflows.

## Usage

Running all the tests in this repo:
`API_KEY=<your api key> SERVER_ADDRESS=<your server's address> pytest . -rP`

Running all the tests in a single file:
- `<your env variables> pytest <path to test file> -rP`

Running a specific test:
- `<your env variables>  pytest . -rP -k '<specific test name>'`

Running tests in parallel, with concurrency 5:
- Install pytest-xdist
- `<your env variables> pytest . -rP -n 5`
