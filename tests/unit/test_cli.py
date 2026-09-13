"""Unit tests for the CLI command parser.

The single most important test here reproduces the exact ``IndexError``
documented in the audit (and the README) when running
``profile CUST-1 update --behavior amount:100``.
"""
from __future__ import annotations

import io
import contextlib

import pytest

from profile_system.cli import ProfileSystemCLI, Profiler


@pytest.fixture
def cli(tmp_path):
    return ProfileSystemCLI(Profiler(storage_file=str(tmp_path / "profiles.json")))


def _capture(cli, command):
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cli.process_command(command)
    return f.getvalue()


def test_help_lists_commands(cli):
    out = _capture(cli, "help")
    assert "profile" in out and "cluster" in out and "exit" in out


def test_documented_profile_update_command_no_longer_crashes(cli):
    """Regression: the original parser raised IndexError on this command."""
    out = _capture(cli, "profile CUST-1 update --behavior amount:100")
    assert "✔ Profile updated for CUST-1" in out


def test_profile_update_with_multiple_behaviors(cli):
    out = _capture(
        cli, "profile CUST-1 update --behavior amount:100 --behavior frequency:5"
    )
    assert "✔ Profile updated for CUST-1" in out
    profile = cli.profiler.tracker.profiles["CUST-1"]
    assert profile.behavioral_signals[-1]["amount"] == 100.0
    assert profile.behavioral_signals[-1]["frequency"] == 5.0


def test_profile_show(cli):
    _capture(cli, "profile CUST-1 update --behavior amount:100")
    out = _capture(cli, "profile CUST-1")
    assert "CUST-1" in out


def test_unknown_command_warns(cli):
    out = _capture(cli, "frobnicate xyz")
    assert "Unknown command" in out


def test_cluster_without_data_warns(cli):
    out = _capture(cli, "cluster")
    assert "⚠" in out


def test_analyze_without_data_warns(cli):
    out = _capture(cli, "analyze anomalies")
    assert "⚠" in out


def test_hitl_validate(cli):
    out = _capture(cli, "hitl validate CUST-1 legitimate user")
    assert "✔ HITL validation added for CUST-1" in out
    assert len(cli.profiler.hitl.validations) == 1


def test_visualize_unknown_entity(cli):
    out = _capture(cli, "visualize NOPE")
    assert "not found" in out.lower()


def test_mode_switch(cli):
    out = _capture(cli, "mode audit")
    assert "✔ Mode switched to audit" in out
    assert cli.current_mode == "audit"


def test_sidebar_toggle(cli):
    out = _capture(cli, "sidebar")
    assert "Sidebar" in out
