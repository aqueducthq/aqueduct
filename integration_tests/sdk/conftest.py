import os

import pytest
import utils

import aqueduct

# Usage: add a <flag> in FLAGS which will enable `--{flag}` in test cmd options.
# The option variable can be accessed through utils.flags during tests.
# One can also mark test to be triggered only when `--{flag}` is turned on through
# @pytest.mark.<flag_name>
FLAGS = [
    "complex_models",
    "publish",
    "requirements",
]


def pytest_addoption(parser):
    for flag in FLAGS:
        parser.addoption(f"--{flag}", action="store_true", default=False)


API_KEY_ENV_NAME = "API_KEY"
SERVER_ADDR_ENV_NAME = "SERVER_ADDRESS"
INTEGRATION = "INTEGRATION"


@pytest.fixture(autouse=True)
def fetch_connected_integration_env_variable():
    utils.integration_name = os.getenv(INTEGRATION)
    yield


@pytest.fixture(autouse=True)
def fetch_flags(pytestconfig):
    for flag in FLAGS:
        utils.flags[flag] = pytestconfig.getoption(flag)
    yield


@pytest.fixture(scope="function")
def client(pytestconfig):
    api_key = os.getenv(API_KEY_ENV_NAME)
    server_address = os.getenv(SERVER_ADDR_ENV_NAME)
    if api_key is None or server_address is None:
        raise Exception(
            "Test Setup Error: api_key and server_address must be set as environmental variables."
        )

    return aqueduct.Client(api_key, server_address)


def pytest_configure(config):
    for flag in FLAGS:
        config.addinivalue_line(
            "markers",
            f"{flag}: mark test to only run if --{flag} command line flag is supplied",
        )


# This allows us to skip tests that depend on command line flags, because pytest.mark.skipif() is evaluated
# before our fixtures are, so we cannot reference fixtures in our test skip condition.
def pytest_runtest_setup(item):
    for flag in FLAGS:
        if flag in item.keywords and not item.config.getoption(f"--{flag}"):
            pytest.skip(f"need --{flag} option to run this test")
