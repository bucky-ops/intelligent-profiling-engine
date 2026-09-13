# Quick Start

## 1. Install

```bash
git clone https://github.com/bucky-ops/intelligent-profiling-engine.git
cd intelligent-profiling-engine

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## 2. Run

### Web (recommended)

```bash
streamlit run app.py
```
Open <http://localhost:8501>.

### Desktop GUI

```bash
python gui_app.py
```

### CLI

```bash
python run.py
```

### Synthetic data generator

```bash
python run_synthetic.py \
    --config config/global_synthetic_config.yaml \
    --domain finance --region NA --size 1000 \
    --output data/output.jsonl
```

## 3. Try the commands

```
> help
> profile CUST-1 update --behavior amount:100 --behavior frequency:5
> profile CUST-1
> cluster --n 3
> analyze anomalies
> visualize CUST-1
> hitl validate CUST-1 "looks like a legitimate customer"
```

## 4. Docker

```bash
make docker
make docker-run
```
