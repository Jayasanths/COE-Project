"""Sensitivity tagger package."""

from .tagger import TAGGER_VERSION, backend_name, split_sentences, tag, tag_session

__all__ = ["tag", "tag_session", "split_sentences", "backend_name", "TAGGER_VERSION"]
