# Test Fixtures

All test fixtures in this directory are synthetic or public domain. They are used
for automated testing of the Research Toolkit's artifact review feature.

## Files

| File | Type | Source | License |
|------|------|--------|---------|
| `sample-ui.png` | PNG image | Synthetically generated (pure Python) | N/A (generated) |
| `sample-chart.png` | PNG image | Synthetically generated (pure Python) | N/A (generated) |
| `sample-report.pdf` | PDF document | Synthetically generated (pure Python) | N/A (generated) |
| `sample-report.md` | Markdown | Written for testing | N/A (generated) |

## Regeneration

The PNG and PDF fixtures can be regenerated using:

```bash
python tests/generate_fixtures.py
```

## Usage

These fixtures are used by:

- `tests/test_review.py` — unit tests with mocked LLM provider
- `tests/test_review_integration.py` — integration tests against CLI
- `tests/test_mime_detection.py` — MIME type detection tests

All tests that need an LLM use fixture replay mode (mocked provider) so they
run without network access in CI.
