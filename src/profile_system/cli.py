"""Command-line interface for the Intelligent Profiling Engine.

Refactored to:
- Use a proper argparse-based subcommand parser (fixes the IndexError on
  `--behavior amount:100` documented in the README).
- Delegate the business logic to a shared :class:`Profiler` service so that
  the CLI, the Tkinter GUI and the Streamlit web app stay in sync.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
from typing import Any, Dict, List, Optional, Tuple

from profile_system.profile import EntityTracker
from profile_system.unsupervised import Clustering, AnomalyDetection
from profile_system.nlp import NLPProcessor
from profile_system.hitl import HITLFeedback
from profile_system.logging_viz import log_event, Visualizer


class Profiler:
    """Shared business-logic service used by every interface.

    Keeping the logic here (instead of inside the CLI / GUI / web classes)
    removes the previous DRY violation where ``handle_cluster`` and
    ``handle_analyze`` were copy-pasted between ``cli.py`` and ``gui_app.py``.
    """

    def __init__(
        self,
        storage_file: str = "profiles.json",
        n_clusters: int = 5,
        contamination: float = 0.1,
    ):
        self.tracker = EntityTracker(storage_file=storage_file)
        self.clustering = Clustering(n_clusters=n_clusters)
        self.anomaly = AnomalyDetection(contamination=contamination)
        self.nlp = NLPProcessor()
        self.hitl = HITLFeedback()
        self.visualizer = Visualizer()

    # ------------------------------------------------------------------ profile
    def update_profile(self, entity_id: str, data: Dict[str, Any]) -> None:
        self.tracker.update_profile(entity_id, data)
        log_event("profile_update", {"entity_id": entity_id})

    def show_profile(self, entity_id: str) -> Dict[str, Any]:
        profile = self.tracker.get_or_create_profile(entity_id)
        return profile.to_dict()

    # ------------------------------------------------------------------ cluster
    def cluster(self, n_clusters: Optional[int] = None) -> Tuple[Any, Any]:
        """Run K-Means clustering on the numeric features of all profiles.

        Returns ``(labels, summary_df)`` or raises ``ValueError`` if there is
        not enough data.
        """
        df = self.tracker.get_profiles_df()
        if df.empty:
            raise ValueError("No data to cluster. Create profiles first.")
        numeric_df = df.select_dtypes(include=["float64", "int64"])
        if numeric_df.empty or numeric_df.shape[0] < 3:
            raise ValueError(
                "Not enough numeric data/profiles for meaningful clustering "
                "(need at least 3)."
            )
        if n_clusters is not None:
            self.clustering = Clustering(n_clusters=n_clusters)
        labels = self.clustering.fit(numeric_df)
        df["cluster"] = labels
        return labels, df[["entity_id", "cluster"]]

    # ----------------------------------------------------------- anomaly detect
    def detect_anomalies(self) -> Tuple[Any, Any]:
        """Run Isolation Forest anomaly detection.

        Returns ``(scores, anomalies_df)``.
        """
        df = self.tracker.get_profiles_df()
        if df.empty:
            raise ValueError("No data to analyze")
        numeric_df = df.select_dtypes(include=["float64", "int64"])
        if numeric_df.empty:
            raise ValueError("No numeric data for anomaly detection.")
        scores = self.anomaly.fit(numeric_df)
        df["anomaly_score"] = scores
        anomalies = df[df["anomaly_score"] < 0]
        return scores, anomalies[["entity_id", "anomaly_score"]]

    # --------------------------------------------------------------- visualise
    def visualize_profile(self, entity_id: str):
        """Visualise the behavioural timeline for ``entity_id``.

        Fixed from the original: the previous implementation looked up the
        ``behavioral_signals`` column on the *flattened* ``get_profiles_df()``
        output, which never exists, raising ``KeyError``. We now read the
        signals directly from the ``Profile`` object.
        """
        profile = self.tracker.profiles.get(entity_id)
        if profile is None:
            raise KeyError(f"Entity '{entity_id}' not found.")
        df = self.tracker.get_profiles_df()
        self.visualizer.plot_profile_timeline(df, entity_id, profile)

    # -------------------------------------------------------------------- hitl
    def add_validation(self, entity_id: str, notes: str) -> None:
        self.hitl.add_validation(
            {"entity_id": entity_id, "validated": True, "notes": notes}
        )
        log_event("hitl_validation", {"entity_id": entity_id, "notes": notes})

    # --------------------------------------------------------------- stats ---
    def stats(self) -> Dict[str, Any]:
        """Return a summary dict of the current engine state."""
        profiles = self.tracker.profiles
        total_signals = sum(len(p.behavioral_signals) for p in profiles.values())
        total_validations = len(self.hitl.validations)
        total_overrides = len(self.hitl.overrides)
        entities_with_text = sum(
            1 for p in profiles.values() if p.text_insights
        )
        return {
            "profile_count": len(profiles),
            "total_behavioral_signals": total_signals,
            "avg_signals_per_profile": (
                round(total_signals / len(profiles), 2) if profiles else 0
            ),
            "entities_with_text_insights": entities_with_text,
            "hitl_validations": total_validations,
            "hitl_overrides": total_overrides,
            "storage_file": self.tracker.storage_file,
        }

    # --------------------------------------------------------------- list ----
    def list_profiles(self) -> List[Dict[str, Any]]:
        """Return a lightweight summary list of all profiles."""
        result = []
        for p in self.tracker.profiles.values():
            result.append({
                "entity_id": p.entity_id,
                "signals": len(p.behavioral_signals),
                "text_insights": len(p.text_insights),
                "updated_at": p.updated_at.isoformat(),
            })
        return result

    # --------------------------------------------------------------- import --
    def import_profiles(self, path: str) -> int:
        """Batch-import profiles from a CSV or JSON file.

        CSV format: ``entity_id,amount,frequency,text`` (text optional).
        JSON format: list of ``{"entity_id": ..., "behavioral": {...}, "text": ...}``.

        Returns the number of profiles imported.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Import file not found: {path}")
        count = 0
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_id = row.get("entity_id") or row.get("id")
                    if not entity_id:
                        continue
                    data: Dict[str, Any] = {}
                    behavioral: Dict[str, Any] = {}
                    for k, v in row.items():
                        if k in ("entity_id", "id"):
                            continue
                        if k == "text":
                            data["text"] = {"sentiment": self.nlp.sentiment_analysis(v)}
                            continue
                        # try numeric
                        try:
                            behavioral[k] = float(v)
                        except (ValueError, TypeError):
                            behavioral[k] = v
                    if behavioral:
                        data["behavioral"] = behavioral
                    self.tracker.update_profile(entity_id, data)
                    count += 1
        elif ext == ".json":
            with open(path, encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, dict):
                # profiles.json format: {entity_id: {profile_dict}}
                for eid, pdata in records.items():
                    profile = self.tracker.get_or_create_profile(eid)
                    profile.static_attributes = pdata.get("static_attributes", {})
                    profile.behavioral_signals = pdata.get("behavioral_signals", [])
                    profile.temporal_patterns = pdata.get("temporal_patterns", {})
                    profile.text_insights = pdata.get("text_insights", {})
                    count += 1
            elif isinstance(records, list):
                for rec in records:
                    eid = rec.get("entity_id")
                    if not eid:
                        continue
                    self.tracker.update_profile(eid, {
                        k: rec[k] for k in ("static", "behavioral", "temporal", "text")
                        if k in rec
                    })
                    count += 1
        else:
            raise ValueError(f"Unsupported import format: {ext}. Use .csv or .json")
        self.tracker.save_profiles()
        log_event("import_profiles", {"path": path, "count": count})
        return count

    # --------------------------------------------------------------- export --
    def export_profiles(self, path: str) -> int:
        """Export all profiles to CSV or JSON. Returns count exported."""
        profiles = self.tracker.profiles
        if not profiles:
            raise ValueError("No profiles to export.")
        ext = os.path.splitext(path)[1].lower()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if ext == ".csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["entity_id", "signal_count", "total_amount",
                                 "avg_amount", "sentiment_polarity", "updated_at"])
                for p in profiles.values():
                    amounts = [s.get("amount", 0) for s in p.behavioral_signals
                               if "amount" in s]
                    sentiment = p.text_insights.get("sentiment", {})
                    writer.writerow([
                        p.entity_id,
                        len(p.behavioral_signals),
                        sum(amounts),
                        round(sum(amounts) / len(amounts), 2) if amounts else 0,
                        sentiment.get("polarity", 0),
                        p.updated_at.isoformat(),
                    ])
        elif ext == ".json":
            data = {pid: p.to_dict() for pid, p in profiles.items()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {ext}. Use .csv or .json")
        log_event("export_profiles", {"path": path, "count": len(profiles)})
        return len(profiles)

    # --------------------------------------------------------------- reset ---
    def reset(self) -> int:
        """Clear all profiles. Returns the number removed."""
        count = len(self.tracker.profiles)
        self.tracker.profiles.clear()
        self.tracker.save_profiles()
        log_event("reset", {"removed": count})
        return count

    # --------------------------------------------------------------- nlp ----
    def analyze_text(self, entity_id: str, text: str) -> Dict[str, Any]:
        """Run full NLP analysis on ``text`` and attach to ``entity_id``."""
        sentiment = self.nlp.sentiment_analysis(text)
        try:
            entities = self.nlp.extract_entities(text)
        except Exception:
            entities = []
        insight = {
            "sentiment": sentiment,
            "entities": entities,
            "text": text[:200],
        }
        self.tracker.update_profile(entity_id, {"text": insight})
        log_event("nlp_analysis", {"entity_id": entity_id})
        return insight


def _parse_kv(token: str) -> Tuple[str, str]:
    """Parse a ``key:value`` token, raising ``ValueError`` on bad input."""
    if ":" not in token:
        raise ValueError(
            f"Expected key:value pair, got '{token}'. "
            "Example: amount:100"
        )
    key, value = token.split(":", 1)
    return key.strip(), value.strip()


class ProfileSystemCLI:
    """Interactive REPL driving :class:`Profiler`."""

    def __init__(self, profiler: Optional[Profiler] = None):
        self.profiler = profiler or Profiler()
        self.sidebar_visible = False
        self.current_mode = "analysis"

    # alias kept for backwards compatibility with gui_app.py
    @property
    def tracker(self):
        return self.profiler.tracker

    @property
    def clustering(self):
        return self.profiler.clustering

    @property
    def anomaly(self):
        return self.profiler.anomaly

    @property
    def nlp(self):
        return self.profiler.nlp

    @property
    def hitl(self):
        return self.profiler.hitl

    @property
    def visualizer(self):
        return self.profiler.visualizer

    def run(self):
        print("Profile System CLI - Type 'help' for commands, 'exit' to quit.")
        self._history: List[str] = []
        import readline  # noqa: F401  optional arrow-key history on POSIX
        while True:
            try:
                command = input(f"{self.current_mode}> ").strip()
                if not command:
                    continue
                if command.lower() == "exit":
                    break
                self._history.append(command)
                self.process_command(command)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"✖ Error: {e}")

    def process_command(self, command: str):
        parts = shlex.split(command)
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]

        handler = {
            "help": lambda a: self.show_help(),
            "profile": self.handle_profile,
            "cluster": self.handle_cluster,
            "analyze": self.handle_analyze,
            "visualize": self.handle_visualize,
            "mode": self.handle_mode,
            "sidebar": lambda a: self.toggle_sidebar(),
            "hitl": self.handle_hitl,
            "stats": lambda a: self.handle_stats(),
            "list": lambda a: self.handle_list(),
            "import": self.handle_import,
            "export": self.handle_export,
            "reset": lambda a: self.handle_reset(),
            "nlp": self.handle_nlp,
        }.get(cmd)
        if handler is None:
            print(f"⚠ Unknown command: {cmd}. Type 'help' for options.")
            return
        handler(args)

    def show_help(self):
        print("""
Available Commands:
  profile <id>                          Show a profile
  profile <id> update --behavior k:v    Add a behavioral signal (e.g. --behavior amount:100)
  profile <id> update --text "<text>"   Add NLP insight from free text
  cluster [--n <k>]                      Run K-Means clustering
  analyze anomalies                      Detect anomalies via Isolation Forest
  visualize <id>                         Plot behavioral timeline for an entity
  nlp <id> "<text>"                      Run full NLP analysis (sentiment + NER)
  hitl validate <id> <notes>             Add HITL validation
  list                                   List all profiles (summary)
  stats                                  Show engine statistics
  import <file.csv|file.json>            Batch-import profiles
  export <file.csv|file.json>            Export all profiles
  reset                                  Clear all profiles (destructive!)
  mode <mode>                            Switch mode (analysis, audit)
  sidebar                                Toggle sidebar
  help                                   Show this help
  exit                                   Quit

Examples:
  profile CUST-1 update --behavior amount:100 --behavior frequency:5
  nlp CUST-1 "Large transaction reported, looks suspicious"
  import data/customers.csv
  export data/export.json
  stats
        """)

    # --------------------------------------------------------------- profile
    def handle_profile(self, args: List[str]):
        parser = argparse.ArgumentParser(prog="profile", add_help=False)
        parser.add_argument("entity_id")
        parser.add_argument(
            "subcommand", nargs="?", choices=["update", "show"], default="show"
        )
        parser.add_argument("--behavior", action="append", default=[])
        parser.add_argument("--text", action="append", default=[])

        try:
            ns = parser.parse_args(args)
        except SystemExit:
            print("⚠ Usage: profile <id> [update|show] "
                  "[--behavior k:v ...] [--text \"...\" ...]")
            return

        if ns.subcommand != "update":
            profile_dict = self.profiler.show_profile(ns.entity_id)
            print(f"Profile for {ns.entity_id}: {json.dumps(profile_dict, indent=2, default=str)}")
            return

        data: Dict[str, Any] = {}
        for token in ns.behavior:
            try:
                key, raw_value = _parse_kv(token)
                try:
                    value: Any = float(raw_value)
                except ValueError:
                    value = raw_value
                data.setdefault("behavioral", {}).update({key: value})
            except ValueError as e:
                print(f"⚠ {e}")
                return

        for text in ns.text:
            data.setdefault("text", {}).update(
                {"sentiment": self.profiler.nlp.sentiment_analysis(text)}
            )

        if not data:
            print("⚠ No updates provided. Use --behavior k:v and/or --text \"...\".")
            return

        self.profiler.update_profile(ns.entity_id, data)
        print(f"✔ Profile updated for {ns.entity_id}")

    # --------------------------------------------------------------- cluster
    def handle_cluster(self, args: List[str]):
        parser = argparse.ArgumentParser(prog="cluster", add_help=False)
        parser.add_argument("--n", type=int, default=None)
        try:
            ns = parser.parse_args(args)
        except SystemExit:
            print("⚠ Usage: cluster [--n <k>]")
            return

        try:
            _, summary_df = self.profiler.cluster(n_clusters=ns.n)
            print("✔ Clustering complete.")
            print(summary_df.to_string(index=False))
        except ValueError as e:
            print(f"⚠ {e}")
        except Exception as e:
            print(f"✖ Clustering failed: {e}")

    # --------------------------------------------------------------- analyze
    def handle_analyze(self, args: List[str]):
        if not args or args[0] != "anomalies":
            print("⚠ Usage: analyze anomalies")
            return
        try:
            _, anomalies_df = self.profiler.detect_anomalies()
            if not anomalies_df.empty:
                print(f"✔ Found {len(anomalies_df)} anomalies:")
                print(anomalies_df.to_string(index=False))
            else:
                print("✔ No anomalies detected.")
        except ValueError as e:
            print(f"⚠ {e}")
        except Exception as e:
            print(f"✖ Anomaly detection failed: {e}")

    # ------------------------------------------------------------- visualize
    def handle_visualize(self, args: List[str]):
        # Fixed: properly parse optional --map flag and entity id in any order
        parser = argparse.ArgumentParser(prog="visualize", add_help=False)
        parser.add_argument("entity_id")
        parser.add_argument("--map", action="store_true")
        try:
            ns = parser.parse_args(args)
        except SystemExit:
            print("⚠ Usage: visualize <id> [--map]")
            return

        try:
            self.profiler.visualize_profile(ns.entity_id)
        except KeyError as e:
            print(f"⚠ {e}")
            ids = list(self.profiler.tracker.profiles.keys())
            if ids:
                print(f"Available profiles: {', '.join(ids[:5])}"
                      + ("..." if len(ids) > 5 else ""))

    # ------------------------------------------------------------------ mode
    def handle_mode(self, args: List[str]):
        if args:
            self.current_mode = args[0]
            print(f"✔ Mode switched to {self.current_mode}")

    # --------------------------------------------------------------- sidebar
    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            profiles = list(self.profiler.tracker.profiles.keys())
            print(f"[ Sidebar ]\nActive Profiles: {len(profiles)}\n"
                  f"Recent: {profiles[-3:] if profiles else 'None'}")
        else:
            print("Sidebar hidden")

    # ------------------------------------------------------------------ hitl
    def handle_hitl(self, args: List[str]):
        parser = argparse.ArgumentParser(prog="hitl", add_help=False)
        sub = parser.add_subparsers(dest="action")
        v = sub.add_parser("validate", add_help=False)
        v.add_argument("entity_id")
        v.add_argument("notes", nargs=argparse.REMAINDER)
        try:
            ns = parser.parse_args(args)
        except SystemExit:
            print("⚠ Usage: hitl validate <id> <notes>")
            return
        if ns.action != "validate" or not ns.entity_id:
            print("⚠ Usage: hitl validate <id> <notes>")
            return
        notes = " ".join(ns.notes) if ns.notes else ""
        self.profiler.add_validation(ns.entity_id, notes)
        print(f"✔ HITL validation added for {ns.entity_id}")

    # ----------------------------------------------------------------- stats
    def handle_stats(self):
        s = self.profiler.stats()
        print("═" * 45)
        print("  Engine Statistics")
        print("═" * 45)
        print(f"  Profiles tracked        : {s['profile_count']}")
        print(f"  Total behavioral signals: {s['total_behavioral_signals']}")
        print(f"  Avg signals / profile   : {s['avg_signals_per_profile']}")
        print(f"  Entities w/ text insights: {s['entities_with_text_insights']}")
        print(f"  HITL validations        : {s['hitl_validations']}")
        print(f"  HITL overrides          : {s['hitl_overrides']}")
        print(f"  Storage file            : {s['storage_file']}")
        print("═" * 45)

    # ------------------------------------------------------------------ list
    def handle_list(self):
        rows = self.profiler.list_profiles()
        if not rows:
            print("⚠ No profiles. Create one with: profile <id> update --behavior amount:100")
            return
        print(f"{'Entity ID':<30} {'Signals':>8} {'Text':>6}  Updated")
        print("─" * 65)
        for r in rows:
            print(f"{r['entity_id']:<30} {r['signals']:>8} {r['text_insights']:>6}  "
                  f"{r['updated_at'][:19]}")
        print(f"─" * 65)
        print(f"Total: {len(rows)} profiles")

    # --------------------------------------------------------------- import
    def handle_import(self, args: List[str]):
        if not args:
            print("⚠ Usage: import <file.csv|file.json>")
            return
        path = args[0]
        try:
            count = self.profiler.import_profiles(path)
            print(f"✔ Imported {count} profiles from {path}")
        except (FileNotFoundError, ValueError) as e:
            print(f"✖ {e}")

    # --------------------------------------------------------------- export
    def handle_export(self, args: List[str]):
        if not args:
            print("⚠ Usage: export <file.csv|file.json>")
            return
        path = args[0]
        try:
            count = self.profiler.export_profiles(path)
            print(f"✔ Exported {count} profiles to {path}")
        except (ValueError, OSError) as e:
            print(f"✖ {e}")

    # ---------------------------------------------------------------- reset
    def handle_reset(self):
        count = self.profiler.reset()
        print(f"✔ Reset complete. Removed {count} profiles.")

    # ------------------------------------------------------------------ nlp
    def handle_nlp(self, args: List[str]):
        parser = argparse.ArgumentParser(prog="nlp", add_help=False)
        parser.add_argument("entity_id")
        parser.add_argument("text")
        try:
            ns = parser.parse_args(args)
        except SystemExit:
            print("⚠ Usage: nlp <id> \"<text>\"")
            return
        try:
            insight = self.profiler.analyze_text(ns.entity_id, ns.text)
            print(f"✔ NLP analysis attached to {ns.entity_id}:")
            print(f"  Sentiment polarity  : {insight['sentiment']['polarity']:.3f}")
            print(f"  Sentiment subjectivity: {insight['sentiment']['subjectivity']:.3f}")
            if insight.get("entities"):
                print("  Entities            :")
                for ent_text, ent_label in insight["entities"]:
                    print(f"    - {ent_text} ({ent_label})")
            else:
                print("  Entities            : (none detected)")
        except Exception as e:
            print(f"✖ NLP analysis failed: {e}")


if __name__ == "__main__":
    cli = ProfileSystemCLI()
    cli.run()
