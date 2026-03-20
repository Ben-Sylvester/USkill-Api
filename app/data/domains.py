"""
8 Built-in domains — each with a 6D feature vector characterising
the domain's intrinsic requirements along temporal, spatial, cognitive,
action, social, and physical axes.
"""

from typing import TypedDict
from app.data.primitives import FeatureVector, DOMAIN_KEYS


class DomainDef(TypedDict):
    id: str
    name: str
    icon: str
    built_in: bool
    feature_vector: FeatureVector
    description: str


BUILT_IN_DOMAINS: list[DomainDef] = [
    {
        "id": "robotics_sim",
        "name": "Robotics Simulation",
        "icon": "🤖",
        "built_in": True,
        "description": "Simulated robotic environments with physics engines.",
        "feature_vector": {
            "temporal": 0.30, "spatial": 0.90, "cognitive": 0.50,
            "action": 0.90, "social": 0.10, "physical": 0.95,
        },
    },
    {
        "id": "robotics_real",
        "name": "Real-World Robotics",
        "icon": "🦾",
        "built_in": True,
        "description": "Physical robotic systems operating in unstructured environments.",
        "feature_vector": {
            "temporal": 0.40, "spatial": 0.88, "cognitive": 0.52,
            "action": 0.88, "social": 0.12, "physical": 0.92,
        },
    },
    {
        "id": "software_dev",
        "name": "Software Dev Agent",
        "icon": "💻",
        "built_in": True,
        "description": "Autonomous software engineering and code manipulation agents.",
        "feature_vector": {
            "temporal": 0.50, "spatial": 0.20, "cognitive": 0.90,
            "action": 0.60, "social": 0.30, "physical": 0.00,
        },
    },
    {
        "id": "education",
        "name": "Education / Tutoring",
        "icon": "🎓",
        "built_in": True,
        "description": "Adaptive learning systems and intelligent tutoring agents.",
        "feature_vector": {
            "temporal": 0.60, "spatial": 0.40, "cognitive": 0.80,
            "action": 0.30, "social": 0.90, "physical": 0.20,
        },
    },
    {
        "id": "medical",
        "name": "Medical / Clinical",
        "icon": "🏥",
        "built_in": True,
        "description": "Clinical decision support, diagnostics, and care-coordination agents.",
        "feature_vector": {
            "temporal": 0.70, "spatial": 0.60, "cognitive": 0.90,
            "action": 0.50, "social": 0.70, "physical": 0.60,
        },
    },
    {
        "id": "finance",
        "name": "Financial Trading",
        "icon": "📈",
        "built_in": True,
        "description": "Algorithmic trading, portfolio management, and risk agents.",
        "feature_vector": {
            "temporal": 0.90, "spatial": 0.10, "cognitive": 0.90,
            "action": 0.70, "social": 0.30, "physical": 0.00,
        },
    },
    {
        "id": "logistics",
        "name": "Logistics / Supply Chain",
        "icon": "🚚",
        "built_in": True,
        "description": "Warehouse, routing, fleet-management, and fulfillment agents.",
        "feature_vector": {
            "temporal": 0.65, "spatial": 0.85, "cognitive": 0.55,
            "action": 0.75, "social": 0.40, "physical": 0.70,
        },
    },
    {
        "id": "game_ai",
        "name": "Game AI",
        "icon": "🎮",
        "built_in": True,
        "description": "NPC behaviour, pathfinding, and decision-making in game engines.",
        "feature_vector": {
            "temporal": 0.55, "spatial": 0.80, "cognitive": 0.70,
            "action": 0.85, "social": 0.50, "physical": 0.60,
        },
    },
]

BUILT_IN_DOMAIN_BY_ID: dict[str, DomainDef] = {d["id"]: d for d in BUILT_IN_DOMAINS}


def get_built_in_domain(domain_id: str) -> DomainDef | None:
    return BUILT_IN_DOMAIN_BY_ID.get(domain_id)


def is_built_in(domain_id: str) -> bool:
    return domain_id in BUILT_IN_DOMAIN_BY_ID


BUILT_IN_DOMAIN_IDS: list[str] = [d["id"] for d in BUILT_IN_DOMAINS]
