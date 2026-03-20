"""
Base Compatibility Matrix (BCM) — empirically derived compatibility scores
between all 8×8 source→target domain pairs.

Values are blended (40%) with the cosine-similarity score (60%) in the
scorer to produce the final compatibility score.

All values are symmetric where physically reasonable but can differ
directionally (e.g. sim→real may differ from real→sim due to sim-to-real gap).
"""

BCM: dict[str, dict[str, float]] = {
    "robotics_sim": {
        "robotics_sim":  1.00,
        "robotics_real": 0.92,
        "software_dev":  0.41,
        "education":     0.34,
        "medical":       0.52,
        "finance":       0.28,
        "logistics":     0.67,
        "game_ai":       0.71,
    },
    "robotics_real": {
        "robotics_sim":  0.88,
        "robotics_real": 1.00,
        "software_dev":  0.38,
        "education":     0.31,
        "medical":       0.55,
        "finance":       0.26,
        "logistics":     0.63,
        "game_ai":       0.64,
    },
    "software_dev": {
        "robotics_sim":  0.39,
        "robotics_real": 0.36,
        "software_dev":  1.00,
        "education":     0.68,
        "medical":       0.62,
        "finance":       0.81,
        "logistics":     0.74,
        "game_ai":       0.72,
    },
    "education": {
        "robotics_sim":  0.29,
        "robotics_real": 0.25,
        "software_dev":  0.62,
        "education":     1.00,
        "medical":       0.71,
        "finance":       0.38,
        "logistics":     0.42,
        "game_ai":       0.55,
    },
    "medical": {
        "robotics_sim":  0.47,
        "robotics_real": 0.51,
        "software_dev":  0.58,
        "education":     0.69,
        "medical":       1.00,
        "finance":       0.41,
        "logistics":     0.52,
        "game_ai":       0.42,
    },
    "finance": {
        "robotics_sim":  0.26,
        "robotics_real": 0.24,
        "software_dev":  0.79,
        "education":     0.39,
        "medical":       0.43,
        "finance":       1.00,
        "logistics":     0.69,
        "game_ai":       0.77,
    },
    "logistics": {
        "robotics_sim":  0.63,
        "robotics_real": 0.60,
        "software_dev":  0.71,
        "education":     0.44,
        "medical":       0.50,
        "finance":       0.67,
        "logistics":     1.00,
        "game_ai":       0.68,
    },
    "game_ai": {
        "robotics_sim":  0.68,
        "robotics_real": 0.61,
        "software_dev":  0.69,
        "education":     0.57,
        "medical":       0.44,
        "finance":       0.74,
        "logistics":     0.72,
        "game_ai":       1.00,
    },
}


def get_base_compat(source: str, target: str) -> float:
    """Return BCM[source][target] or 0.5 as neutral fallback."""
    return BCM.get(source, {}).get(target, 0.5)


# Alias used by routers/domains.py and app/data/__init__.py
BASE_COMPAT_MATRIX = BCM
