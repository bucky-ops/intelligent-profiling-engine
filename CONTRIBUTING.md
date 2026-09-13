# Contributing to the Intelligent Profiling Engine

Thanks for your interest in contributing! This document describes how to set
up a development environment and the conventions we follow.

## 1. Development setup

```bash
git clone https://github.com/bucky-ops/intelligent-profiling-engine.git
cd intelligent-profiling-engine

python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m spacy download en_core_web_sm
pre-commit install
```

## 2. Project layout

```
src/profile_system/   Core engine: Profile, Clustering, AnomalyDetection, NLP, HITL
src/generator/        Synthetic-data generator (config-driven orchestrator + domains)
app.py                Streamlit web app
gui_app.py            Tkinter desktop GUI
run.py                CLI entrypoint
run_synthetic.py      Synthetic-data CLI
tests/                Pytest test suite (unit + integration)
```

## 3. Coding standards

- **Python**: 3.9+ (CI matrix: 3.9 / 3.10 / 3.11 / 3.12).
- **Style**: enforced by `ruff` and `ruff-format`. Run `pre-commit run --all-files`.
- **Types**: type hints are encouraged; `mypy src` should not regress.
- **Tests**: every new feature or bug fix should ship with a test. Aim for
  ≥60 % coverage on `src/`.
- **Commits**: use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## 4. Pull request flow

1. Fork the repo, create a branch named `feature/<short-description>` or `fix/<issue-id>`.
2. Make your changes, keep commits atomic.
3. Run: `ruff check src tests && pytest`.
4. Open a PR against `main`. CI must pass before merge.
5. Request one review. Maintainers squash-merge.

## 5. Reporting bugs / security issues

- Bugs: open a [GitHub Issue](https://github.com/bucky-ops/intelligent-profiling-engine/issues)
  with a minimal reproducible example.
- Security: **do not** open a public issue. See [SECURITY.md](SECURITY.md).

## 6. Branch protection

The `main` branch is protected: PR review + passing CI is required. Direct
pushes to `main` are not allowed.

## 7. Releases

Releases follow [Semantic Versioning](https://semver.org/) and are tagged
`v0.X.Y`. A GitHub Release is published with auto-generated notes.
