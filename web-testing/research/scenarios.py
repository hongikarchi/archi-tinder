"""
scenarios.py -- Maps a persona to a test scenario with swipe decision logic.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from .persona import PersonaProfile


@dataclass
class TestScenario:
    persona: PersonaProfile
    search_query: str
    decide_swipe: Callable  # (card_metadata: dict, persona: PersonaProfile) -> 'like' | 'dislike'
    max_swipes: int = 30
    generate_report: bool = True


def _keyword_overlap_score(card_metadata: dict, persona: PersonaProfile) -> float:
    """
    Compute a simple keyword overlap score between a building card and persona preferences.
    Returns a float between 0.0 and 1.0.
    """
    prefs = persona.taste_preferences
    score = 0.0
    total_weight = 0.0

    # Program match (weight 3)
    card_program = (card_metadata.get('axis_typology') or '').strip()
    preferred_programs = [p.lower() for p in prefs.get('preferred_programs', [])]
    if card_program:
        total_weight += 3.0
        if card_program.lower() in preferred_programs:
            score += 3.0

    # Style match (weight 2)
    card_style = (card_metadata.get('axis_style') or '').strip().lower()
    preferred_styles = [s.lower() for s in prefs.get('preferred_styles', [])]
    if card_style:
        total_weight += 2.0
        for ps in preferred_styles:
            if ps in card_style or card_style in ps:
                score += 2.0
                break

    # Atmosphere match (weight 2)
    card_atmo = (card_metadata.get('axis_atmosphere') or '').strip().lower()
    preferred_atmos = [a.lower() for a in prefs.get('preferred_atmospheres', [])]
    if card_atmo:
        total_weight += 2.0
        for pa in preferred_atmos:
            if pa in card_atmo:
                score += 2.0
                break

    # Material match (weight 1)
    card_materials = card_metadata.get('axis_material_visual') or []
    if isinstance(card_materials, str):
        card_materials = [card_materials]
    card_material_text = (card_metadata.get('axis_material') or '').lower()
    preferred_materials = [m.lower() for m in prefs.get('preferred_materials', [])]
    if card_materials or card_material_text:
        total_weight += 1.0
        card_mat_lower = [m.lower() for m in card_materials] + [card_material_text]
        for pm in preferred_materials:
            if any(pm in cm for cm in card_mat_lower):
                score += 1.0
                break

    if total_weight == 0:
        return 0.5  # No data to compare -- coin flip

    return score / total_weight


class _SwipeTracker:
    """Tracks swipe history to ensure minimum like rate for test progression."""
    def __init__(self, max_swipes: int = 30):
        self.total = 0
        self.likes = 0
        self._max_swipes = max_swipes

    def decide(self, card_metadata: dict, persona: PersonaProfile) -> str:
        score = _keyword_overlap_score(card_metadata, persona)
        self.total += 1

        # Target ~35% like rate (~10 likes in 30 swipes) for convergence.
        # Backend needs: 3 likes → 'analyzing', then 3+ delta samples below threshold.
        # Avoid consecutive forced likes — the frontend's swipedCardId guard
        # blocks rapid same-direction swipes if the animation hasn't completed.
        target_like_rate = 0.35
        current_rate = self.likes / max(self.total - 1, 1)

        # Force like every few swipes if below target (never two forced likes in a row)
        if current_rate < target_like_rate and self.total > 5 and self.total % 3 == 0:
            self.likes += 1
            return 'like'

        # Like if score matches persona preferences
        if score >= 0.2:
            self.likes += 1
            return 'like'

        return 'dislike'


def decide_swipe(card_metadata: dict, persona: PersonaProfile) -> str:
    """
    Decide whether to like or dislike a card based on persona preferences.
    Uses keyword overlap scoring with a low threshold of 0.2.
    Returns 'like' or 'dislike'.
    """
    score = _keyword_overlap_score(card_metadata, persona)
    return 'like' if score >= 0.2 else 'dislike'


def build_scenario(persona: PersonaProfile, max_swipes: int = 30) -> TestScenario:
    """
    Build a test scenario from a persona profile.

    Args:
        persona: The persona to test with.
        max_swipes: Maximum number of swipes before stopping (default: 30).

    Returns:
        TestScenario instance.
    """
    tracker = _SwipeTracker(max_swipes=max_swipes)
    return TestScenario(
        persona=persona,
        search_query=persona.search_query,
        decide_swipe=tracker.decide,
        max_swipes=max_swipes,
        generate_report=True,
    )
