# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- GitHub Actions CI running tests on Python 3.9–3.13 plus a ruff lint job.
- GitHub Actions workflow for trusted publishing to PyPI on release.
- `CONTRIBUTING.md`, issue templates, and PR template.
- README badges, comparison table, and runnable code preview at the top.

### Changed
- Project URLs in `pyproject.toml` now point to the actual GitHub repository.
- Bumped classifier to `Development Status :: 4 - Beta` and added `Typing :: Typed`.

## [0.1.0] - 2026-04-24

### Added
- Initial release.
- `PCloudClient` with `userinfo`, folder listing, `ensure_folder`, file
  upload/download/delete, and directory backup helpers.
- OAuth 2.0 helpers: `build_authorize_url`, `parse_authorization_response`,
  `exchange_code`.
- CLI: `auth-url`, `exchange-code`, `ls`, `mkdir`, `upload`, `download`,
  `backup-dir`, `delete`.
- US/EU pCloud host support via the `hostname` redirect parameter.
