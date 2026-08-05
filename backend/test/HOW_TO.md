# Test Execution Guide

Welcome to the automated testing suite for this project. This guide will walk you through how to execute both module-level and project-level tests using `pytest`.

## Prerequisites

Ensure you have installed all the necessary dependencies by running:
```bash
pip install -r requirements.txt
```
*(Note: `pytest` and `pytest-md` have been added to `requirements.txt` to support testing and markdown report generation.)*

## Test Structure

- **`module_testing/`**: Contains unit tests isolated to individual modules (e.g., `data_layer`, `security_layer`, etc.).
- **`project_testing/`**: Contains end-to-end integration tests that ensure all modules work together correctly.
- **`reports.md`**: Each test directory generates a `reports.md` file which logs the test outputs for review.

## How to Run Tests

### Running All Tests
To run all tests and see the output in the console:
```bash
python -m pytest test/
```

### Running Module-Specific Tests
To run tests for a specific module (e.g., `data_layer`) and save the results to its `reports.md`:
```bash
python -m pytest test/module_testing/data_layer/ -v > test/module_testing/data_layer/reports.md
```

### Running Project-Level Tests
To run the full project tests and save the results:
```bash
python -m pytest test/project_testing/ -v > test/project_testing/reports.md
```

### Generating Markdown Reports Automatically
If you are using `pytest-md`, you can also automatically generate markdown reports using its plugins if configured in your pytest setup.

Happy testing!
