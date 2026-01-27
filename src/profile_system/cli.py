import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from profile_system.profile import EntityTracker
from profile_system.unsupervised import Clustering, AnomalyDetection
from profile_system.nlp import NLPProcessor
from profile_system.hitl import HITLFeedback
from profile_system.logging_viz import log_event, Visualizer
import pandas as pd

class ProfileSystemCLI:
    def __init__(self):
        self.tracker = EntityTracker()
        self.clustering = Clustering()
        self.anomaly = AnomalyDetection()
        self.nlp = NLPProcessor()
        self.hitl = HITLFeedback()
        self.visualizer = Visualizer()
        self.sidebar_visible = False
        self.current_mode = "analysis"

    def run(self):
        print("Profile System CLI - Type 'help' for commands, 'exit' to quit.")
        while True:
            try:
                command = input(f"{self.current_mode}> ").strip()
                if not command:
                    continue
                if command.lower() == 'exit':
                    break
                self.process_command(command)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"✖ Error: {e}")

    def process_command(self, command):
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == 'help':
            self.show_help()
        elif cmd == 'profile':
            self.handle_profile(args)
        elif cmd == 'cluster':
            self.handle_cluster(args)
        elif cmd == 'analyze':
            self.handle_analyze(args)
        elif cmd == 'visualize':
            self.handle_visualize(args)
        elif cmd == 'mode':
            self.handle_mode(args)
        elif cmd == 'sidebar':
            self.toggle_sidebar()
        elif cmd == 'hitl':
            self.handle_hitl(args)
        else:
            print(f"⚠ Unknown command: {cmd}. Type 'help' for options.")

    def show_help(self):
        print("""
Available Commands:
- profile <id> [options]: Manage profiles (e.g., profile update CUST-1 --behavior amount:100)
- cluster [options]: Run clustering (e.g., cluster --n 3)
- analyze anomalies: Detect anomalies
- visualize <id> --map: Show profile map
- mode <mode>: Switch mode (analysis, audit)
- sidebar: Toggle sidebar
- hitl validate <id> <notes>: Add HITL validation
- help: Show this help
- exit: Quit
        """)

    def handle_profile(self, args):
        if not args:
            print("⚠ Usage: profile <id> [update|show] [options]")
            return
        entity_id = args[0]
        if len(args) > 1 and args[1] == 'update':
            # Parse options like --behavior amount:100
            data = {}
            for arg in args[2:]:
                if arg.startswith('--behavior'):
                    # Simple parse
                    kv = arg.split('--behavior ')[1].split(':')
                    data['behavioral'] = {kv[0]: float(kv[1])}
                elif arg.startswith('--text'):
                    text = arg.split('--text ')[1]
                    data['text'] = {'sentiment': self.nlp.sentiment_analysis(text)}
            self.tracker.update_profile(entity_id, data)
            print(f"✔ Profile updated for {entity_id}")
            log_event("profile_update", {"entity_id": entity_id})
        else:
            profile = self.tracker.get_or_create_profile(entity_id)
            print(f"Profile for {entity_id}: {profile.to_dict()}")

    def handle_cluster(self, args):
        df = self.tracker.get_profiles_df()
        if df.empty:
            print("⚠ No data to cluster. Create profiles first.")
            return
            
        # Select numeric columns for clustering
        numeric_df = df.select_dtypes(include=['float64', 'int64'])
        if numeric_df.empty or numeric_df.shape[0] < 3: # Basic check for enough data
             print("⚠ Not enough numeric data/profiles for meaningful clustering (need at least 3).")
             return

        try:
            labels = self.clustering.fit(numeric_df)
            df['cluster'] = labels
            print(f"✔ Clustering complete.")
            print(df[['entity_id', 'cluster']].to_string(index=False))
        except Exception as e:
            print(f"✖ Clustering failed: {e}")

    def handle_analyze(self, args):
        if args and args[0] == 'anomalies':
            df = self.tracker.get_profiles_df()
            if df.empty:
                print("⚠ No data to analyze")
                return
            
            numeric_df = df.select_dtypes(include=['float64', 'int64'])
            if numeric_df.empty:
                print("⚠ No numeric data for anomaly detection.")
                return

            try:
                scores = self.anomaly.fit(numeric_df)
                df['anomaly_score'] = scores
                # IsolationForest: -1 is anomaly, 1 is normal
                anomalies = df[df['anomaly_score'] < 0]
                
                if not anomalies.empty:
                    print(f"✔ Found {len(anomalies)} anomalies:")
                    print(anomalies[['entity_id', 'anomaly_score']].to_string(index=False))
                else:
                    print("✔ No anomalies detected.")
            except Exception as e:
                print(f"✖ Anomaly detection failed: {e}")

    def handle_visualize(self, args):
        if args and '--map' in args:
            entity_id = args[0]
            df = self.tracker.get_profiles_df()
            self.visualizer.plot_profile_timeline(df, entity_id)  # Would show plot if GUI

    def handle_mode(self, args):
        if args:
            self.current_mode = args[0]
            print(f"✔ Mode switched to {self.current_mode}")

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            # Show summary
            profiles = list(self.tracker.profiles.keys())
            print(f"[ Sidebar ]\nActive Profiles: {len(profiles)}\nRecent: {profiles[-3:] if profiles else 'None'}")
        else:
            print("Sidebar hidden")

    def handle_hitl(self, args):
        if args and args[0] == 'validate':
            entity_id = args[1]
            notes = ' '.join(args[2:])
            self.hitl.add_validation({'entity_id': entity_id, 'validated': True, 'notes': notes})
            print(f"✔ HITL validation added for {entity_id}")

if __name__ == "__main__":
    cli = ProfileSystemCLI()
    cli.run()