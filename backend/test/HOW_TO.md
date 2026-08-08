# Testing Guide

This directory contains the test suite for the Multi-Modal RAG backend. We use `pytest` as our testing framework.

## Prerequisites

Ensure you have installed the testing dependencies, generally included in your main `requirements.txt` or a separate `requirements-dev.txt`:
```bash
pip install pytest pytest-asyncio httpx
```

## Test Structure

The tests are categorized into two main folders:

1. **`module_testing/`**: Contains unit tests for individual components and modules (e.g., cache tiers, tokenizers, vector stores).
2. **`project_testing/`**: Contains end-to-end integration tests, system-level flows, and stress tests ensuring all parts work together correctly.

*Note: Tests involve generating inferences using the **Mistral-7B-Instruct-v0.2** model.*

## How to Run Tests

### Running All Tests
To execute the entire test suite across all modules and projects:
```bash
pytest test/ -v
```

### Running Project Tests Specifically
To run the integration and system tests:
```bash
pytest test/project_testing/ -v
```

**Normal Tests vs Stress Tests:**
Inside `project_testing/`, some tests simulate high load, concurrent users, or large data volumes (stress testing). If these are marked, you can run them specifically, or run everything together using the command above.

### Generating Reports
To generate a comprehensive markdown report (useful for CI/CD or documentation), you can use pytest reporting plugins (e.g., `pytest-md` if installed), or pipe the output:
```bash
pytest test/ -v > reports.md
# Or if using a specific markdown plugin:
pytest test/ --md=reports.md
```
