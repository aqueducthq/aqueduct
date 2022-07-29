This suite of tests is meant to provide coverage for our requirements story.

To run, you must set the `--requirements` flag in your pytest command (every test case should be marked with `@pytest.mark.requirements`). Your pytest command must be run from the *parent* directory. For example:

```
API_KEY=<API_KEY> INTEGRATION=<INTEGRATION> SERVER_ADDRESS=<ADDRESS> pytest ./requirements_tests -rP --requirements 
```

Becuase each of these tests will uninstall and reinstall a python package, there *cannot be any parallelism* when running these tests.