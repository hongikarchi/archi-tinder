"""
persona.py -- Persona generation for E2E visual testing.
Supports template mode (random combos from pools) and LLM mode (Gemini).
"""
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# -- Pools for template-mode generation --

NAMES = [
    'Alex Chen', 'Maria Santos', 'Yuki Tanaka', 'James Wright',
    'Priya Sharma', 'Sofia Rossi', 'Omar Hassan', 'Lin Wei',
    'Emma Nielsen', 'Carlos Mendez', 'Aisha Patel', 'Tomas Novak',
]

OCCUPATIONS = [
    'Architecture Student', 'Interior Designer', 'Urban Planner',
    'Real Estate Developer', 'Landscape Architect', 'Structural Engineer',
    'Art Curator', 'Design Journalist', 'Homeowner', 'Civil Engineer',
    'Photography Enthusiast', 'Construction Manager',
]

STYLES = [
    'Minimalist', 'Brutalist', 'Contemporary', 'Classical', 'Deconstructivist',
    'Art Deco', 'Gothic', 'High-Tech', 'Organic', 'Postmodern',
    'Vernacular', 'Industrial', 'Parametric', 'Tropical Modern',
]

PROGRAMS = [
    'Housing', 'Office', 'Museum', 'Education', 'Religion', 'Sports',
    'Transport', 'Hospitality', 'Healthcare', 'Public', 'Mixed Use',
    'Landscape', 'Infrastructure', 'Other',
]

MATERIALS = [
    'concrete', 'glass', 'steel', 'wood', 'brick', 'stone',
    'bamboo', 'copper', 'titanium', 'terracotta', 'rammed earth',
]

ATMOSPHERES = [
    'serene', 'dramatic', 'intimate', 'monumental', 'playful',
    'austere', 'warm', 'ethereal', 'raw', 'fluid',
    'atmospheric', 'luminous', 'grounded', 'soaring',
]

SEARCH_TEMPLATES = [
    'I want a {style} {program} with lots of {material}',
    'Show me {atmosphere} buildings in {style} style',
    'Find me a {program} that feels {atmosphere} and uses {material}',
    '{style} architecture with {atmosphere} atmosphere',
    'Modern {program} made of {material} and {material2}',
    'I like {atmosphere}, {atmosphere2} spaces for {program}',
]


@dataclass
class PersonaProfile:
    name: str
    age: int
    occupation: str
    taste_preferences: Dict = field(default_factory=dict)
    search_query: str = ''
    swipe_strategy_description: str = ''

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> 'PersonaProfile':
        return cls(**data)


def _build_search_query(prefs: dict) -> str:
    """Build a natural-language search query from taste preferences."""
    template = random.choice(SEARCH_TEMPLATES)
    style = random.choice(prefs.get('preferred_styles', ['Contemporary']))
    program = random.choice(prefs.get('preferred_programs', ['Housing'])).lower()
    material = random.choice(prefs.get('preferred_materials', ['concrete']))
    material2 = random.choice(prefs.get('preferred_materials', ['glass']))
    atmosphere = random.choice(prefs.get('preferred_atmospheres', ['serene']))
    atmosphere2 = random.choice(prefs.get('preferred_atmospheres', ['warm']))

    return template.format(
        style=style,
        program=program,
        material=material,
        material2=material2,
        atmosphere=atmosphere,
        atmosphere2=atmosphere2,
    )


def _build_swipe_strategy(prefs: dict) -> str:
    """Describe how the persona will swipe based on preferences."""
    styles = ', '.join(prefs.get('preferred_styles', [])[:2])
    programs = ', '.join(prefs.get('preferred_programs', [])[:2])
    return (
        f"Likes {styles} style buildings, especially {programs}. "
        f"Prefers {', '.join(prefs.get('preferred_atmospheres', [])[:2])} atmospheres. "
        f"Drawn to {', '.join(prefs.get('preferred_materials', [])[:2])} materials."
    )


def generate_persona(mode: str = 'template') -> PersonaProfile:
    """
    Generate a persona profile.

    Args:
        mode: 'template' for random combo from pools,
              'llm' for Gemini-generated persona (requires GEMINI_API_KEY env var).

    Returns:
        PersonaProfile instance.
    """
    if mode == 'template':
        return _generate_template_persona()
    elif mode == 'llm':
        return _generate_llm_persona()
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'template' or 'llm'.")


def _generate_template_persona() -> PersonaProfile:
    """Generate a persona from random template pools."""
    prefs = {
        'preferred_styles': random.sample(STYLES, k=random.randint(2, 4)),
        'preferred_programs': random.sample(PROGRAMS, k=random.randint(1, 3)),
        'preferred_materials': random.sample(MATERIALS, k=random.randint(2, 3)),
        'preferred_atmospheres': random.sample(ATMOSPHERES, k=random.randint(2, 4)),
    }

    return PersonaProfile(
        name=random.choice(NAMES),
        age=random.randint(22, 55),
        occupation=random.choice(OCCUPATIONS),
        taste_preferences=prefs,
        search_query=_build_search_query(prefs),
        swipe_strategy_description=_build_swipe_strategy(prefs),
    )


def _generate_llm_persona() -> PersonaProfile:
    """Generate a persona using Gemini LLM."""
    import os
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError(
            "google-generativeai is required for LLM mode. "
            "Install it: pip install google-generativeai"
        )

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        # Try reading from backend/.env
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'backend', '.env',
        )
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GEMINI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment or backend/.env")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    prompt = f"""Generate a fictional persona who is interested in architecture.
Return ONLY valid JSON with this exact structure:
{{
  "name": "Full Name",
  "age": 30,
  "occupation": "Job Title",
  "taste_preferences": {{
    "preferred_styles": ["Style1", "Style2"],
    "preferred_programs": ["Program1", "Program2"],
    "preferred_materials": ["material1", "material2"],
    "preferred_atmospheres": ["atmosphere1", "atmosphere2"]
  }},
  "search_query": "A natural language architecture search query",
  "swipe_strategy_description": "How this person would evaluate buildings"
}}

Use only these program types: {', '.join(PROGRAMS)}
Use styles from: {', '.join(STYLES)}
Use materials from: {', '.join(MATERIALS)}
Use atmospheres from: {', '.join(ATMOSPHERES)}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])

    data = json.loads(text)
    return PersonaProfile.from_dict(data)
