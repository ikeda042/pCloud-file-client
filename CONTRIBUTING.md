# Contributing

Thanks for considering a contribution! This project is small on purpose, but
fixes, docs improvements, and pCloud API coverage are all welcome.

## Dev setup

```bash
python -m pip install -e ".[dev]"
```

## Run the test suite

```bash
python -m unittest discover -s tests -v
```

Tests use a fake `requests` session, so they do not call the real pCloud API.
Please keep it that way — no live network calls in unit tests.

## Lint

```bash
ruff check .
```

## Style

- Type-annotate new public functions.
- Keep the public surface in `pcloud_client/__init__.py` minimal and explicit.
- Prefer `folderid` / `fileid` over path-only operations where the pCloud API
  recommends it.
- Don't introduce new runtime dependencies beyond `requests` without discussion.

## Pull requests

- Open a draft PR early if you want feedback on direction.
- Reference any related issue in the PR description.
- Include a short note in `CHANGELOG.md` under `## [Unreleased]`.

## Reporting issues

Please use the issue templates in `.github/ISSUE_TEMPLATE/`. For anything that
might involve credentials or tokens, **redact them before posting**.

## Security

If you find a security issue, please do not open a public issue. Open a private
GitHub Security Advisory on the repo instead.
