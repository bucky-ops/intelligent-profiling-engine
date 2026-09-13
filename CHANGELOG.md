# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025 - Audit remediation release

This release implements the recommendations of the v0.1 audit. The project
is now runnable end-to-end and ships with tests, CI and Docker.

### Fixed
- `src/generator/terminal_ui.py`: hard `SyntaxError` (mis-indented `else:`).
- `src/profile_system/cli.py`: the documented command
  `profile CUST-1 update --behavior amount:100` no longer raises
  `IndexError`. A proper `argparse`-based parser now handles
  `--behavior k:v` and `--text "..."`.
- `src/profile_system/cli.py`: `visualize <id> --map` no longer treats
  `--map` as the entity id. Argument order is now flexible.
- `src/profile_system/logging_viz.py`: `Visualizer.plot_profile_timeline`
  no longer raises `KeyError` - it accepts the `Profile` object directly
  instead of looking up a non-existent DataFrame column.
- `config/global_synthetic_config.yaml`: `finance`/`ngo`/`telecom`/`traffic`
  are no longer wrongly nested under `regions:`.
- `gui_app.py`: removed the unsafe `os._exit(0)` call on window close;
  shutdown now flushes the store and joins the worker thread cleanly.
- `requirements.txt`: regenerated from real, currently-available PyPI
  versions. The previous file contained fictional future pins
  (`torch==2.10.0`, `pyspark==4.1.1`, `transformers==4.57.6`) that caused
  `pip install` to fail. Removed 10 dead dependencies.

### Added
- `pyproject.toml` replaces `setup.py`. Pinning happens in one place.
- `requirements-dev.txt` for test / lint tooling.
- `Profiler` service in `src/profile_system/cli.py` - shared business
  logic for CLI / GUI / web (DRY).
- Batched (write-behind) persistence in `EntityTracker`.
- Lazy NLP model loading + embedding cache in `NLPProcessor`.
- Public API exports in `src/profile_system/__init__.py`.
- `tests/` directory with 37 unit + integration tests.
- `.github/workflows/ci.yml`: lint + type-check + test matrix on Python
  3.9 - 3.12, plus a dedicated security job (`pip-audit`, `bandit`).
- `.github/dependabot.yml`: weekly pip + GitHub-Actions updates.
- `.pre-commit-config.yaml`: ruff + format + hygiene hooks.
- `CONTRIBUTING.md`, `SECURITY.md`, `ARCHITECTURE.md`, `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` (this file).
- `Dockerfile` + `docker-compose.yml` + `.env.example` + `Makefile`.
- `mkdocs` configuration and `docs/` folder.

### Changed
- `README.md`: fixed `git origin push` typo, added prerequisites,
  troubleshooting and contributor links.

## [0.1.0] - Initial public release

- CLI, Tkinter GUI and Streamlit web app.
- K-Means clustering, Isolation Forest anomaly detection, spaCy NLP,
  HITL feedback.
- Synthetic-data generator (finance, NGO, telecom, traffic).
