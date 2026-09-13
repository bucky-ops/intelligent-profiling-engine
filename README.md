# Intelligent Profiling Engine (Nexus) 🚀

[![CI](https://github.com/bucky-ops/intelligent-profiling-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/bucky-ops/intelligent-profiling-engine/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Interface-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![codecov](https://img.shields.io/badge/coverage-37%20tests-brightgreen)](https://github.com/bucky-ops/intelligent-profiling-engine/actions)

A state-of-the-art **Intelligent Profiling Engine** that combines Unsupervised
Machine Learning, Natural Language Processing (NLP), and Human-in-the-Loop
(HITL) feedback to track, analyze, and evolve entity profiles in real-time.

> **v0.2.0** — Audit remediation release. See the
> [audit report](AUDIT_REPORT.md) and the [changelog](CHANGELOG.md) for the
> full list of fixes, or [ARCHITECTURE.md](ARCHITECTURE.md) for the design.

---

## 🌟 Key Features

- **🧠 Hybrid Intelligence**: K-Means clustering + Isolation Forest anomaly detection with debounced JSON persistence.
- **💬 NLP-Driven Insights**: spaCy NER + TextBlob sentiment + SentenceTransformer embeddings — loaded lazily with caching.
- **👥 Human-in-the-Loop (HITL)**: validations + overrides stored alongside profiles.
- **🖥️ Triple-Mode Interface**: CLI (`run.py`), Tkinter desktop (`gui_app.py`), Streamlit web (`app.py`).
- **📈 Temporal Evolution**: behavioral signals timestamped with timezone-aware datetimes.
- **🛠️ Synthetic Data**: config-driven generator for finance, NGO, telecom, traffic across 7 world regions.

---

## 🛠️ Tech Stack

- **Core**: Python 3.9+
- **ML**: scikit-learn (K-Means, Isolation Forest)
- **NLP**: spaCy, TextBlob, sentence-transformers
- **Data**: pandas, NumPy
- **Interfaces**: Streamlit (web), Tkinter (desktop)
- **Visualisation**: matplotlib
- **Packaging**: `pyproject.toml` (PEP 621)
- **CI/CD**: GitHub Actions + Dependabot + pre-commit

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/bucky-ops/intelligent-profiling-engine.git
cd intelligent-profiling-engine

python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

For development / tests:
```bash
pip install -r requirements-dev.txt
pre-commit install
```

### 2. Launching the System

#### Web Interface (Recommended)
```bash
streamlit run app.py
```

#### Desktop GUI
```bash
python gui_app.py
```

#### Interactive CLI
```bash
python run.py
```

#### Synthetic Data Generator
```bash
python run_synthetic.py \
    --config config/global_synthetic_config.yaml \
    --domain finance --region NA --size 1000 \
    --output data/output.jsonl
```

### 3. Try the Commands

```
> help
> profile CUST-1 update --behavior amount:100 --behavior frequency:5
> profile CUST-1
> cluster --n 3
> analyze anomalies
> visualize CUST-1
> hitl validate CUST-1 "looks like a legitimate customer"
> exit
```

### 4. Docker (optional)

```bash
make docker
make docker-run         # starts the Streamlit app on http://localhost:8501
```

---

## 📂 Project Structure

```
src/profile_system/    Core engine: Profile, Clustering, AnomalyDetection, NLP, HITL
src/generator/         Synthetic-data generator (config-driven orchestrator + domains)
app.py                 Streamlit web application
gui_app.py             Tkinter desktop application
run.py                 CLI entrypoint
run_synthetic.py       Synthetic-data CLI
tests/                 Pytest test suite (unit + integration)
docs/                  mkdocs documentation source
config/                YAML config for the synthetic generator
Dockerfile             Multi-stage container image
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design.

---

## 🧪 Testing & Quality

```bash
make test              # run pytest
make test-cov          # run pytest with coverage
make lint              # ruff
make type              # mypy
make security          # pip-audit + bandit
```

CI runs on Python 3.9 / 3.10 / 3.11 / 3.12 on every push and PR.

---

## 🚢 Deployment

- **Docker**: see `Dockerfile` and `docker-compose.yml`.
- **Environment variables**: see `.env.example`.
- **Production checklist**: see [SECURITY.md](SECURITY.md).

---

## 📚 Documentation

- [Architecture](ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)
- [Audit Report](AUDIT_REPORT.md)
- [Profiling Algorithm Guide](profiling_algorithm_guide.md)
- [Interface Design](interface_design.md)
- [Whitepaper](whitepaper/proposal.md)

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md)
and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'feat: add AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Nexus Profile System** - *Bridging the gap between raw data and actionable intelligence.*
