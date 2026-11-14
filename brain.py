# brain.py — Backward compatibility re-export
"""
Re-exports the complete Brain implementation from core.brain.
Eliminates duplicate code between root and core packages.
"""
from core.brain import Brain

__all__ = ["Brain"]
