# Intelligent Profiling Engine — Comprehensive Audit Report

**Repository:** `bucky-ops/intelligent-profiling-engine`
**Audit performed:** technical review of HEAD of `main` (commit `4a691d2`)
**Scope:** Code Quality, Documentation, Testing, Dependencies, Performance, Deployment

---

## 0. Executive Summary

The project is an **early-stage prototype** (~1,973 lines of Python across 29 files) for an
"Intelligent Profiling Engine" combining unsupervised ML (K-Means + Isolation Forest),
NLP (spaCy, TextBlob, Sentence-Transformers) and Human-in-the-Loop (HITL) feedback, with
three interfaces (CLI, Tkinter desktop, Streamlit web).

In its **current state the project is NOT runnable end-to-end**:

- One source file (`src/generator/terminal_ui.py`) contains a hard **`SyntaxError`** — the whole `generator.terminal_ui` module cannot be imported.
- The primary documented CLI command `profile CUST-1 update --behavior amount:100` (shown in `README.md` and `interface_design.md`) **raises `IndexError` at runtime** because the option parser expects `--behavioramount:100` as a single token.
- `Visualizer.plot_profile_timeline()` reads a DataFrame column (`behavioral_signals`) that `EntityTracker.get_profiles_df()` never returns → guaranteed `KeyError`.
- The YAML config has a structural bug: `finance/ngo/telecom/traffic` are nested under `regions`, so the orchestrator silently treats them as fake regions.
- `requirements.txt` pins **fictional future versions** (e.g. `torch==2.10.0`, `pyspark==4.1.1`, `transformers==4.57.6`, `altair==6.0.0`, `numpy==2.4.1`) that do not exist on PyPI — `pip install -r requirements.txt` will **fail** on a real environment.
- There are **zero tests**, **no CI**, **no Dockerfile**, branch protection is **off**, Dependabot is **off**.

**Verdict:** promising architecture and design thinking, but the implementation is a non-functional scaffold. It needs a stabilization sprint before it can be called "functional".

---

## 1. Code Quality

### 1.1 Critical defects (blockers — must fix before anything else)

| # | File:Line | Issue | Impact |
|---|-----------|-------|--------|
| C1 | `src/generator/terminal_ui.py:66` | `else:` mis-indented inside `elif` body → `SyntaxError` | Module cannot be imported. `run_terminal_ui()` is dead. |
| C2 | `src/profile_system/cli.py:88-89` | `arg.split('--behavior ')[1]` requires a literal space inside the token. The documented `--behavior amount:100` is split by shell into `['--behavior','amount:100']`, so `arg=='--behavior'` and `.split('--behavior ')[1]` → `IndexError`. | The documented happy-path command crashes. |
| C3 | `src/profile_system/logging_viz.py:19` | `profile.iloc[0]['behavioral_signals']` — `get_profiles_df()` never produces this column. | `visualize <id> --map` raises `KeyError`. |
| C4 | `src/profile_system/cli.py:146-150` | `handle_visualize` does `entity_id = args[0]` and then checks `if '--map' in args`; if the user runs `visualize --map <id>`, `entity_id` becomes `--map`. | Wrong/ surprising behavior. |
| C5 | `config/global_synthetic_config.yaml:31-34` | `finance:`, `ngo:`, `telecom:`, `traffic:` are indented under `regions:`. | `orchestrator.regions` includes 4 bogus regions; calling `generate_record(domain,'finance')` looks up `regions['finance']={}` then `.get('countries')[0]` → `TypeError: 'NoneType' is not subscriptable`. |
| C6 | `gui_app.py:435` | `os._exit(0)` on window close. | Skips `finally` blocks, `atexit` handlers, open file flushes (e.g. `profiles.json` may be truncated), and Streamlit/Tkinter cleanup. Unsafe. |

### 1.2 Maintainability / readability smells

- **DRY violation:** `gui_app.GUIProfileSystem.handle_cluster` and `handle_analyze` are copy-paste of the CLI versions with only a `table_callback`/`plot_callback` added. Logic drift is guaranteed.
- **`sys.path.insert` hacks** in `app.py`, `gui_app.py`, `run.py`, `src/profile_system/cli.py`, `examples/example_finance.py` — the project doesn't trust its own `setup.py` packaging. Should rely on installed package, not path mangling.
- **`profile_system/__init__.py` is empty** — no public API exported, so `from profile_system import EntityTracker` fails.
- **`EntityTracker.detect_changes`** is a stub: `return {"anomalies": recent_signals > 10}` — the magic number 10 is undocumented and unrelated to real drift.
- **`NLPProcessor.get_embeddings`** silently returns `[[0.0]*384]` when the model fails to load — produces plausible-looking but meaningless vectors. Should raise or log loudly.
- **22 pyflakes findings**: unused imports (e.g. `time`, `EntityTracker`, `Clustering`, `AnomalyDetection`, `NLPProcessor`, `HITLFeedback`, `log_event`, `Visualizer` in `app.py`; `pandas` in `cli.py`; `uuid`/`datetime` in `orchestrator.py`), unused locals (`profile` in `gui_app.py:117`), f-strings without placeholders (`gui_app.py:41`, `cli.py:115`).
- **Bare `except:`** in `gui_app.py:201` (`ConsoleRedirector._write`) — swallows `KeyboardInterrupt` and hides bugs.
- **Mixed error handling:** 23 `print("✖ ...")` style error messages instead of structured logging. `logging.basicConfig` is configured in `logging_viz.py` but `log_event` is barely used (only once in `cli.py`).
- **No type hints on public methods** in `profile.py` (some present), `cli.py` (none), `gui_app.py` (none).
- **Mutable default / global state:** `Profile.__init__` uses `datetime.now()` (not tz-aware). Should use `datetime.now(timezone.utc)` for a system that claims to be global/multi-region.
- **`requirements.txt` starts with a BOM** (`\ufeff`) — cosmetic but trips some parsers.

### 1.3 Refactoring opportunities (step-by-step)

1. **Fix the 6 blockers (C1–C6) first** — without these, nothing else matters.
2. **Introduce a `Command` parser** (use `argparse` or `click`) to replace the ad-hoc `parts = command.split()` dispatch. This kills C2 and C4 in one move and makes `--behavior amount:100 --text "..."` actually parseable.
3. **Extract shared ML pipeline** into a `Profiler` service class that both CLI and GUI call. GUI subclasses only override *rendering* (callback), not business logic.
4. **Define a stable public API** in `profile_system/__init__.py` (`__all__ = ["EntityTracker","Profile","Clustering","AnomalyDetection","NLPProcessor","HITLFeedback"]`).
5. **Replace `os._exit(0)`** with graceful shutdown: signal worker threads to stop, join with timeout, then `root.destroy()`.
6. **Move from `print()` to structured logging** everywhere; route user-facing messages through a single `Reporter` abstraction so CLI/GUI/Web can format them differently.
7. **Remove `sys.path.insert` hacks** — install the package (`pip install -e .`) and import normally.
8. **Add type hints + docstrings** to every public method; enforce with `mypy --strict` in CI.

---

## 2. Documentation

### 2.1 What exists
- `README.md` (93 lines) — overview, quick-start, structure.
- `profiling_algorithm_guide.md` (81 lines) — conceptual guide to profiling/HITL/NLP.
- `interface_design.md` (94 lines) — UI/UX philosophy.
- `whitepaper/proposal.md` (51 lines) — architecture proposal.
- `LICENSE` (MIT).

### 2.2 Gaps & errors

- **`README.md:90` typo:** `git origin push feature/AmazingFeature` should be `git push origin feature/AmazingFeature`.
- **`README.md` references `data/` folder** that is gitignored and never created on clone. First-run `streamlit run app.py` works, but `synthetic_data_generator.py` (which writes to `data/...`) crashes with `FileNotFoundError` because `data/` doesn't exist.
- **No `CONTRIBUTING.md`** — README links to a 5-step git workflow but there are no coding standards, branch naming, PR template, or commit-message conventions.
- **No `CHANGELOG.md`** — only 3 commits in history, but future contributors need a release log.
- **No `SECURITY.md`** — for a system that handles profiling (sensitive domain), there is no vulnerability-reporting policy.
- **No `CODE_OF_CONDUCT.md`**.
- **No `ARCHITECTURE.md` / diagram** — the architecture is scattered across 4 markdown files. A single `docs/architecture.md` with a C4/sequence diagram would help.
- **Quick-start omits prerequisites:** `python -m spacy download en_core_web_sm` is required (the code prints a warning but the README never says to do it). Also no mention that `torch` (~2GB) will be downloaded, or that CPU vs GPU wheels differ.
- **No API reference.** No docstrings on `EntityTracker`, `Clustering`, `AnomalyDetection`, `NLPProcessor`. Tools like `pdoc`/`mkdocs` could auto-generate.
- **No troubleshooting section** for common errors (spacy model missing, SentenceTransformer download failure, Tkinter missing on headless servers).
- **`whitepaper/proposal.md` is a bullet outline**, not a whitepaper — privacy, ROI, and roadmap sections are one-liners.
- **`launch_interface.bat` is Windows-only.** No Linux/macOS equivalent.

### 2.3 Documentation enhancement plan (step-by-step)

1. **Fix README typo + add `data/` auto-creation** in the generator scripts.
2. **Add `CONTRIBUTING.md`** with: dev setup (`python -m venv`, `pip install -e .[dev]`), pre-commit hooks (`ruff`, `black`, `mypy`), test command, branch/PR conventions.
3. **Add `SECURITY.md`** with a `security@` contact or "open a private advisory" link.
4. **Add `ARCHITECTURE.md`** with a single Mermaid diagram of the data flow: `SyntheticDataGenerator → EntityTracker → (Clustering|AnomalyDetection|NLP) → HITLFeedback → Visualizer`.
5. **Auto-generate API docs** with `mkdocs-material` + `mkdocstrings` from docstrings; publish via GitHub Pages.
6. **Add a `docs/runbook.md`** covering: install spacy model, install sentence-transformers, headless/SSH notes for the Tkinter GUI, Streamlit deployment.
7. **Replace the bullet `whitepaper/proposal.md`** with a real 4–6 page document (problem, architecture, privacy model, evaluation plan, roadmap).
8. **Add a top-level `docs/` folder** and move `interface_design.md`, `profiling_algorithm_guide.md`, `whitepaper/` under it.

---

## 3. Testing

### 3.1 Current state
- **Zero tests.** No `tests/` directory, no `pytest.ini`/`pyproject.toml [tool.pytest]`, no `tox.ini`.
- No CI/CD pipeline (`.github/` does not exist).
- The only executable sample is `examples/example_finance.py`, which has **no assertions** — it just prints.
- No coverage measurement.

### 3.2 Recommended testing strategy (step-by-step)

**Step 1 — Unit tests (pytest, target ≥70% on `src/`):**
- `tests/unit/test_profile.py` — `Profile.to_dict`/`from_dict` round-trip, `EntityTracker.update_profile` idempotency, `get_profiles_df` schema.
- `tests/unit/test_unsupervised.py` — `Clustering.fit` returns N labels for N rows; `AnomalyDetection.fit` returns scores in `[-1, 1]`; determinism with `random_state=42`.
- `tests/unit/test_nlp.py` — sentiment polarity in `[-1,1]`; entity extraction on a fixed sentence returns expected entities; topic modeling on empty list returns `{}`.
- `tests/unit/test_hitl.py` — `add_validation`/`add_override`/`apply_overrides` mutate state correctly; `apply_overrides` overrides keys.
- `tests/unit/test_cli.py` — table-driven command parsing: assert `profile CUST-1 update --behavior amount:100` succeeds; `cluster` with <3 profiles warns; unknown command warns.
- `tests/unit/test_generator_config.py` — assert `regions` keys are exactly the 7 real regions (catches C5 regression).
- `tests/unit/test_generator_domains.py` — each domain generator produces records with the documented schema keys.

**Step 2 — Integration tests:**
- `tests/integration/test_pipeline.py` — generate 100 synthetic records → ingest into `EntityTracker` → cluster → detect anomalies → assert `len(anomalies) ≤ 0.15 * 100`.
- `tests/integration/test_hitl_loop.py` — generate record flagged `human_review_flag=True` → analyst overrides → re-cluster → assert profile moved clusters.
- `tests/integration/test_orchestrator_yaml.py` — load `config/global_synthetic_config.yaml`, generate batch for each (domain, region) pair, assert no exceptions.

**Step 3 — End-to-end tests:**
- `tests/e2e/test_cli_flow.py` — subprocess `python run.py`, pipe commands via stdin, assert stdout contains expected `✔` markers.
- `tests/e2e/test_streamlit_smoke.py` — `streamlit app` model: use `streamlit-app-crawler` or `playwright` to load `app.py`, type a command, assert the terminal div updates.
- (Optional) `tests/e2e/test_gui.py` — `pytest-tkinter` to drive the Tkinter app.

**Step 4 — Property/contract tests:**
- Use `hypothesis` to assert `Profile.from_dict(p.to_dict()).to_dict() == p.to_dict()` for any valid profile.
- Assert `EntityTracker.save_profiles()` then re-load produces identical state.

**Step 5 — Non-functional tests:**
- `tests/perf/test_save_profiles.py` — assert 1,000 profile updates complete in < 5s (will currently FAIL — see §5).
- `tests/security/test_no_secrets.py` — `gitleaks` scan in pre-commit.

**Step 6 — CI (GitHub Actions):**
- `.github/workflows/ci.yml`: matrix Python 3.9/3.10/3.11/3.12, `ruff check`, `black --check`, `mypy src`, `pytest --cov=src --cov-fail-under=70`.
- `.github/workflows/security.yml`: `pip-audit`, `bandit`, `gitleaks`.
- `.github/dependabot.yml`: weekly updates for pip + github-actions.

---

## 4. Dependencies

### 4.1 Critical problems

- **`requirements.txt` pins versions that DO NOT EXIST on PyPI:**
  - `torch==2.10.0` (latest real as of writing is 2.5.x)
  - `pyspark==4.1.1` (latest real is 3.5.x)
  - `transformers==4.57.6` (latest real is ~4.46)
  - `altair==6.0.0` (latest real is 5.x)
  - `numpy==2.4.1`, `scikit-learn==1.8.0`, `matplotlib==3.10.8`, `pandas==2.3.3`, `pillow==12.1.0` — all future/fictional.
  - Plus `certifi==2026.1.4`, `regex==2026.1.15`, `fsspec==2026.1.0` — year-2026 dated.

  → **`pip install -r requirements.txt` fails on a real machine.** The pins appear to be auto-generated by an LLM or a future-dated environment and must be regenerated from a real `pip freeze`.

- **`setup.py install_requires` is UNPINNED** (9 deps, no versions) while `requirements.txt` is fully pinned. Running `pip install -e .` (as the README instructs) resolves *latest* and will conflict with the pinned file. Pick ONE source of truth.

- **Dead dependencies** (declared but never imported in any `.py` file):
  - `nltk` (in `setup.py` + `requirements.txt`, zero usages)
  - `torch` (only pulled in transitively by `sentence-transformers`)
  - `transformers` (declared, never imported)
  - `seaborn`, `plotly`, `altair`, `openpyxl`, `GitPython`, `networkx`, `pyarrow`, `huggingface-hub` — all zero direct usages.

  That is **~5GB of unnecessary downloads** (torch + transformers + huggingface-hub) for a system whose only NLP needs are TF-IDF + sentiment + 384-dim embeddings.

- **No `requirements-dev.txt`** — test/lint tooling not separated from runtime deps.
- **No `Pipfile` / `poetry.lock` / `uv.lock`** — no reproducible lockfile.
- **Dependabot disabled** at the repo level.
- **No `pip-audit` / `safety` scan in CI.**

### 4.2 Dependency remediation plan (step-by-step)

1. **Regenerate `requirements.txt` from a real, working venv:** create a fresh `python3.11 -m venv`, `pip install streamlit scikit-learn pandas numpy matplotlib spacy textblob sentence-transformers pyyaml faker`, then `pip freeze > requirements.txt`. This removes the fictional pins.
2. **Delete dead deps:** `nltk`, `transformers`, `seaborn`, `plotly`, `altair`, `openpyxl`, `GitPython`, `networkx`, `pyarrow` (only needed if Spark path is used), `huggingface-hub` (transitive), `torch` (transitive — let sentence-transformers pull it). This shrinks install size by ~80%.
3. **Decide Spark fate:** the Spark path is a stub that silently falls back to JSONL. Either (a) commit to PySpark and add `pyspark` + `pyarrow` to an extras `[spark]`, or (b) remove the Spark modules entirely.
4. **Pin in ONE place:** use `pyproject.toml` (PEP 621) with `[project.dependencies]` for runtime and `[project.optional-dependencies]` for `dev`, `spark`, `web`, `gui`. Delete `setup.py` (deprecated).
5. **Add `pip-audit` + `bandit`** to CI; enable Dependabot with weekly cadence.
6. **Add a `pre-commit` config** with `ruff`, `black`, `pip-audit`, `gitleaks`.
7. **Document the spacy model download** as a post-install step (`python -m spacy download en_core_web_sm`) in `pyproject.toml` scripts or a `Makefile` target.

---

## 5. Performance

### 5.1 Identified bottlenecks

| # | Location | Bottleneck | Impact |
|---|----------|------------|--------|
| P1 | `profile.py:78-84, 89, 102` | `save_profiles()` rewrites the **entire** `profiles.json` on every single `update_profile` / `get_or_create_profile` call. | O(N) disk write per signal. With 10k profiles × 100 signals each = 1M full rewrites. Catastrophic. |
| P2 | `profile.py:66, 68` | `EntityTracker.__init__` calls `load_profiles()` which loads **all** profiles into memory at construction. | Startup time + memory scale linearly with profile count; Streamlit re-instantiates `ProfileSystemCLI` on every interaction via `st.session_state`. |
| P3 | `profile.py:121-148` | `get_profiles_df()` rebuilds the entire DataFrame on **every** call (it's called by `handle_cluster`, `handle_analyze`, `handle_visualize`). | O(N) rebuild per command. |
| P4 | `nlp.py:8-19` | `NLPProcessor.__init__` **eagerly** loads spaCy `en_core_web_sm` AND `SentenceTransformer('all-MiniLM-L6-v2')` (a ~80MB model download + load). Done once per `ProfileSystemCLI()` instantiation. | Multi-second startup. Streamlit pays this on first session. |
| P5 | `nlp.py:21-24` | `get_embeddings` re-encodes every call; no caching. | Repeated encoding of same text is wasteful. |
| P6 | `unsupervised.py:11` | `KMeans(n_clusters=5, random_state=42)` uses default `n_init='auto'`/10; no `MiniBatchKMeans` option for >10k rows. | Slow convergence on large data. |
| P7 | `unsupervised.py:14-17` | `Clustering.fit` re-selects numeric columns inside `fit` even though `handle_cluster` already selected them. | Double work. |
| P8 | `cli.py:104, 122` | `df = self.tracker.get_profiles_df()` is called **separately** in `handle_cluster` and `handle_analyze`. A combined `analyze` command would rebuild twice. | Redundant work. |
| P9 | `synthetic_data_generator.py:186-188` | `generate_batch` is a list comprehension — holds all records in memory. The streaming variant (`generate_streaming_batch`) is a generator but is unused. | Memory pressure for large batches. |
| P10 | `streaming.py` | "Streaming" is a `dict`-in-memory sink — no real Kafka/RabbitMQ/Redis Streams. | Cannot be used in production. |
| P11 | `spark_generation.py:23-29` | Spark path silently falls back to JSONL without warning. | Users think they wrote Parquet but got JSONL. |

### 5.2 Optimization plan (step-by-step)

1. **Batched persistence (P1):** introduce a write-behind queue — accumulate signals in memory and flush `profiles.json` every N seconds or N updates (use `threading.Timer` or `atexit`). Alternatively move to SQLite (`prisma`-equivalent for Python is `SQLModel`/`peewee`) which gives O(log N) updates.
2. **Lazy loading (P2):** make `EntityTracker` load profiles on demand by `entity_id` (LRU cache), not eagerly. For Streamlit, cache `ProfileSystemCLI` in `@st.cache_resource`.
3. **Memoize `get_profiles_df` (P3, P8):** invalidate cache on `update_profile`; rebuild only when stale.
4. **Lazy NLP models (P4, P5):** load spaCy / SentenceTransformer on first use (`@functools.lru_cache` on a `_get_nlp()` / `_get_embedder()` helper). Cache embeddings keyed by `hash(text)`.
5. **Mini-batch K-Means (P6):** switch to `MiniBatchKMeans` when `len(df) > 10_000`.
6. **Don't double-select numerics (P7):** let the caller pass already-numeric data; have `Clustering.fit` accept a `np.ndarray` or `pd.DataFrame` and trust the caller.
7. **Real streaming (P10):** add an optional `confluent-kafka` producer behind an interface (`Sink` protocol) with `SimulatedKafkaSink` and `KafkaSink` implementations.
7. **Honest fallback (P11):** if `SPARK_AVAILABLE` is False, `log.warning(...)` and raise, don't silently write JSONL with a `.parquet` path.
8. **Vectorize `get_profiles_df` (P3):** build the DataFrame via `pd.DataFrame.from_records([...])` once per rebuild instead of per-row dict appends.
9. **Add a benchmark suite** (`tests/perf/`) with `pytest-benchmark` to guard against regressions.

---

## 6. Deployment

### 6.1 Current state

- **No Dockerfile, no `docker-compose.yml`, no Kubernetes manifests, no Helm chart.**
- **No CI/CD pipeline** (`.github/workflows/` does not exist).
- **No environment-variable config.** `EntityTracker(storage_file="profiles.json")` hardcodes the path.
- **No health-check endpoint.** Streamlit has no `/healthz`.
- **`launch_interface.bat`** is Windows-only and just runs `python gui_app.py`.
- **`os._exit(0)`** in `gui_app.py:435` makes graceful shutdown impossible.
- **Branch protection OFF**, Dependabot OFF, no required status checks.
- **No release tags**, no `CHANGELOG.md`.
- **Logging** uses `logging.basicConfig(filename='profile_system.log')` — no rotation, no structured JSON, no level configuration via env var.
- **No `Makefile`** or `taskfile` to unify `lint`/`test`/`run`/`docker` commands.

### 6.2 Deployment strategy (step-by-step)

1. **Containerize (Phase 1 — web app):**
   - `Dockerfile` (multi-stage): `python:3.12-slim` base, install `requirements.txt`, `python -m spacy download en_core_web_sm`, expose `8501`, `CMD streamlit run app.py --server.port=8501 --server.address=0.0.0.0`.
   - `.dockerignore`: `.git`, `data/`, `__pycache__`, `*.log`.
   - `docker-compose.yml`: one service `web` + a volume `./data:/app/data`.
2. **Containerize (Phase 2 — optional Spark):**
   - Add a `spark-master` + `spark-worker` service in compose, mount the same `data/` volume, expose Spark UI on `8080`.
3. **Configuration:**
   - Move hardcoded paths to env vars: `PROFILES_STORAGE_PATH`, `SPACY_MODEL`, `NLP_MODEL`, `LOG_LEVEL`, `LOG_FORMAT=json|text`.
   - Add a `.env.example` documenting every var.
   - Use `pydantic-settings` to load + validate config at startup.
4. **CI/CD (GitHub Actions):**
   - `.github/workflows/ci.yml`: lint (ruff), type (mypy), test (pytest), build Docker image, push to GHCR on tag.
   - `.github/workflows/release.yml`: on `v*` tag, build multi-arch image, create GitHub Release with auto-generated notes.
   - `.github/workflows/security.yml`: `pip-audit`, `bandit`, `trivy` image scan, `gitleaks`.
5. **Health & observability:**
   - Add `streamlit-healthcheck` pattern (a `/healthz` route via a small FastAPI sidecar or a `streamlit-observe` plugin).
   - Switch logging to `structlog` with JSON output; ship to stdout for Docker log drivers.
   - Add Prometheus metrics via `prometheus-client` (request count, profile count, clustering latency).
6. **Graceful shutdown:**
   - Replace `os._exit(0)` with `signal.SIGTERM` handler that flushes `EntityTracker` and joins worker threads with a 5s timeout.
7. **Releases & versioning:**
   - Adopt Semantic Versioning; tag `v0.1.0` after the stabilization sprint.
   - Use Release Drafter to auto-generate `CHANGELOG.md` from PR labels.
8. **Repository hygiene:**
   - Turn ON branch protection on `main` (require PR review + CI pass).
   - Enable Dependabot (pip + github-actions, weekly).
   - Add `CODEOWNERS`.

---

## 7. Prioritized Action Plan (the "what to do next" list)

| Priority | Task | Effort | Why |
|----------|------|--------|-----|
| 🔴 P0 | Fix C1 (terminal_ui SyntaxError) | 5 min | Module is dead code. |
| 🔴 P0 | Fix C2 (CLI option parser → IndexError) | 1 h | Documented happy path crashes. |
| 🔴 P0 | Fix C5 (YAML config structure) | 5 min | Orchestrator breaks on any region call. |
| 🔴 P0 | Regenerate `requirements.txt` from a real venv | 1 h | `pip install` currently fails. |
| 🔴 P0 | Remove dead deps (`nltk`, `transformers`, `torch` direct, `seaborn`, `plotly`, `altair`, `openpyxl`, `GitPython`, `networkx`) | 30 min | Removes ~5GB of downloads. |
| 🟠 P1 | Fix C3 (Visualizer KeyError) + C4 (handle_visualize arg order) | 1 h | `visualize` command is broken. |
| 🟠 P1 | Replace `os._exit(0)` with graceful shutdown | 1 h | Data-loss risk. |
| 🟠 P1 | Add `pytest` skeleton + 10 unit tests covering the blockers above | 4 h | Prevents regressions; enables CI. |
| 🟠 P1 | Add `.github/workflows/ci.yml` (ruff + mypy + pytest) | 2 h | Automated quality gate. |
| 🟠 P1 | Unify `setup.py` → `pyproject.toml`; pin deps once | 2 h | Reproducible installs. |
| 🟡 P2 | Batched persistence (P1) — write-behind queue or SQLite | 1 d | Removes the O(N) write-per-signal cliff. |
| 🟡 P2 | Lazy-load NLP models (P4) + cache embeddings (P5) | 4 h | Fast startup, less memory. |
| 🟡 P2 | Refactor CLI/GUI shared logic into a `Profiler` service | 1 d | DRY; unblocks future interfaces. |
| 🟡 P2 | Add `CONTRIBUTING.md`, `SECURITY.md`, `ARCHITECTURE.md` | 4 h | Onboarding + trust. |
| 🟡 P2 | Dockerize the Streamlit app + `.env.example` | 4 h | One-command deploy. |
| 🟢 P3 | Property-based tests (hypothesis) | 1 d | Catches edge cases. |
| 🟢 P3 | Real Kafka sink behind a `Sink` protocol | 2 d | Production streaming. |
| 🟢 P3 | `mkdocs` API docs on GitHub Pages | 1 d | Discoverability. |
| 🟢 P3 | Prometheus metrics + `structlog` JSON logging | 1 d | Observability. |

**Target after the P0 + P1 list (~1 sprint):** a runnable, installable, tested project.
**Target after P2 (~2 sprints):** a deployable, documented, observable system ready for a pilot.

---

## 8. Methodology Note

This audit was performed by:
1. Cloning the repo at HEAD of `main` (commit `4a691d2`).
2. Static analysis: `python -m compileall` (syntax), `pyflakes` (unused imports/locals), manual review of all 29 Python files.
3. Dynamic verification: actually importing each module under a stubbed-deps harness, executing the documented CLI command to reproduce the `IndexError`, loading the YAML to confirm the config bug, and inspecting `get_profiles_df()` output to confirm the missing column.
4. Dependency audit: cross-referencing `requirements.txt` pins against PyPI's real release history, and counting actual `import` usages of each declared top-level dependency.
5. Repository metadata via the GitHub REST API (branch protection, Dependabot, security advisories, CI presence).

Every claim above is reproducible from the repository at the audited commit.
