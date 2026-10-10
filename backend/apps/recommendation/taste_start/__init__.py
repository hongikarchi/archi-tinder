"""
taste_start -- Tag recognition for the Taste-tab start flow.

Public API:
  recognize_tags(text, prev_tags) -> RecognitionResult   (JEV, dictionary fallback)
  Tag                                                    (JSON-serialisable tag)
  JevUnavailable                                         (JEV failure signal)
  parse_years(text)                                      (numeric year range rule)
"""
from .jev_client import JevUnavailable
from .recognizer import RecognitionResult, Tag, recognize_tags
from .year_rule import parse_years

__all__ = ['recognize_tags', 'RecognitionResult', 'Tag', 'JevUnavailable', 'parse_years']
