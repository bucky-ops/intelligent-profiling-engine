# Architecture

## High-level data flow

```
┌─────────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ SyntheticData-      │───>│   EntityTracker   │───>│   Profiler       │
│   Generator         │    │ (batched writes)  │    │  (service layer) │
│ (4 domains,         │    │ profiles.json     │    │                  │
│  7 regions,          │    └──────────────────┘    └────────┬─────────┘
│  streaming)           │                                      │
└─────────────────────┘                   ┌────────────────────┼────────────────────┐
                                          │                    │                    │
                                          ▼                    ▼                    ▼
                                ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐
                                │  Clustering  │   │ AnomalyDetection │   │  NLPProcessor│
                                │  (K-Means)   │   │ (IsolationForest) │   │ (spaCy/ST)   │
                                └──────────────┘   └──────────────────┘   └──────────────┘
                                          │                    │                    │
                                          └────────────┬───────┴────────────────────┘
                                                       ▼
                                              ┌─────────────────┐
                                              │  HITLFeedback   │
                                              │ (validations +  │
                                              │  overrides)     │
                                              └────────┬────────┘
                                                       ▼
                                              ┌─────────────────┐
                                              │   Visualizer    │
                                              │ (matplotlib)    │
                                              └────────┬────────┘
                                                       ▼
                                ┌───────────────────────┴───────────────────────┐
                                │           Interfaces (thin wrappers)          │
                                ├─────────────┬──────────────┬──────────────────┤
                                │  CLI (REPL) │ Tkinter GUI  │ Streamlit web    │
                                └─────────────┴──────────────┴──────────────────┘
```

## Key design principles

1. **Single source of truth.** All business logic lives in the
   `Profiler` service (`src/profile_system/cli.py`). The CLI, the Tkinter GUI
   and the Streamlit app are thin wrappers that only render results. This
   eliminates the previous DRY violation where `handle_cluster` /
   `handle_analyze` were copy-pasted between `cli.py` and `gui_app.py`.

2. **Batched persistence.** `EntityTracker` debounces disk writes: it
   buffers updates in memory and flushes `profiles.json` either after 2
   seconds of inactivity, after 50 updates, or at process exit (via
   `atexit`). This replaced the original O(N) "rewrite everything on every
   update" behaviour.

3. **Lazy model loading.** `NLPProcessor` loads spaCy and
   SentenceTransformer on first use, so the CLI starts in milliseconds when
   NLP features aren't needed. Embeddings are cached by `hash(text)`.

4. **Config-driven generation.** The synthetic-data orchestrator reads a
   single YAML file (`config/global_synthetic_config.yaml`) describing the
   regions, domains and output format. Adding a new domain = one new class
   under `src/generator/domains/` + one line in the orchestrator's
   `domain_generators` dict.

5. **Graceful shutdown.** The Tkinter GUI uses a thread-safe command queue
   and replaces the unsafe `os._exit(0)` with a clean teardown that flushes
   the profile store and joins the worker thread.

## Package layout

| Package / file | Responsibility |
|----------------|----------------|
| `src/profile_system/profile.py` | `Profile` + `EntityTracker` (batched persistence) |
| `src/profile_system/unsupervised.py` | K-Means clustering + Isolation Forest anomaly detection |
| `src/profile_system/nlp.py` | spaCy NER + TextBlob sentiment + SentenceTransformer embeddings |
| `src/profile_system/hitl.py` | Human-in-the-loop validations + overrides |
| `src/profile_system/logging_viz.py` | Structured logging + matplotlib visualisations |
| `src/profile_system/cli.py` | `Profiler` service + `ProfileSystemCLI` REPL |
| `src/generator/` | Config-driven synthetic-data generator |
| `app.py` | Streamlit web interface |
| `gui_app.py` | Tkinter desktop interface |
| `run.py` / `run_synthetic.py` | CLI entrypoints |

## Threading model (GUI)

```
UI thread (Tk mainloop)
   │  user types command
   ▼
command queue  ───────────►  worker thread (daemon)
   ▲                              │  Profiler.*()
   │  after(0, callback)          ▼
   │                         ConsoleRedirector (thread-safe)
   └── writes to Text widget
```

The worker thread is woken by `queue.Queue.get(timeout=0.2)`, processes one
command at a time, and uses `root.after(0, ...)` to push results back to the
UI thread. On shutdown, the UI thread signals `is_alive = False` and enqueues
`None` to unblock the worker, then joins it with a 2 s timeout.
