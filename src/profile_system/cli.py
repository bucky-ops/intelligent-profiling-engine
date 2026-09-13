"""Command-line interface for the Intelligent Profiling Engine.

Refactored to:
- Use a proper argparse-based subcommand parser (fixes the IndexError on
  `--behavior amount:100` documented in the README).
- Delegate the business logic to a shared :class:`Profiler` service so that
  the CLI, the Tkinter GUI and the Streamlit web app stay in sync.
"""
from __future__ import annotations

import argparse
import json
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
        while True:
            try:
                command = input(f"{self.current_mode}> ").strip()
                if not command:
                    continue
                if command.lower() == "exit":
                    break
                self.process_command(command)
            except KeyboardInterrupt:
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

        if cmd == "help":
            self.show_help()
        elif cmd == "profile":
            self.handle_profile(args)
        elif cmd == "cluster":
            self.handle_cluster(args)
        elif cmd == "analyze":
            self.handle_analyze(args)
        elif cmd == "visualize":
            self.handle_visualize(args)
        elif cmd == "mode":
            self.handle_mode(args)
        elif cmd == "sidebar":
            self.toggle_sidebar()
        elif cmd == "hitl":
            self.handle_hitl(args)
        else:
            print(f"⚠ Unknown command: {cmd}. Type 'help' for options.")

    def show_help(self):
        print("""
Available Commands:
- profile <id>                          Show a profile
- profile <id> update --behavior k:v    Add a behavioral signal (e.g. --behavior amount:100)
- profile <id> update --text "<text>"   Add NLP insight from free text
- cluster [--n <k>]                      Run K-Means clustering
- analyze anomalies                      Detect anomalies via Isolation Forest
- visualize <id>                         Plot behavioral timeline for an entity
- mode <mode>                            Switch mode (analysis, audit)
- sidebar                                Toggle sidebar
- hitl validate <id> <notes>            Add HITL validation
- help                                   Show this help
- exit                                   Quit
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


if __name__ == "__main__":
    cli = ProfileSystemCLI()
    cli.run()
