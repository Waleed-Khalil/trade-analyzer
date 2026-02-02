"""
Trading journal: auto-log PLAY signals, update with exit (P/L, R multiple), summary report.
"""

from journal.journal import get_journal_path, log_play_signal

__all__ = ["get_journal_path", "log_play_signal"]
