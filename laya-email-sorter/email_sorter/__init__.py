"""Gmail inbox sorter built on laya's System 1 decision engine.

Two fast passes, no generation:
  1. header rules (List-Unsubscribe, no-reply senders, Gmail's own category labels)
  2. one laya forward pass per email answering a few typed questions

The result is a plan: which emails stay in the inbox (and why) and which can be archived.
Nothing is ever deleted. Archiving only happens with `--apply`, and it only removes the
INBOX label, so every archived email is still in All Mail and search.
"""
from .sorter import Decision, EmailSorter, sort_questions

__all__ = ["Decision", "EmailSorter", "sort_questions"]
