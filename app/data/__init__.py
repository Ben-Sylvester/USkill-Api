"""
Data layer — primitives taxonomy, feature vectors, base compatibility matrix,
and built-in domain definitions.

This module re-exports every symbol that the service layer imports from `app.data`.
"""

from app.data.bcm import BASE_COMPAT_MATRIX, get_base_compat
from app.data.domains import (
    BUILT_IN_DOMAINS,
    BUILT_IN_DOMAIN_BY_ID,
    BUILT_IN_DOMAIN_IDS,
    get_built_in_domain,
    is_built_in,
)
from app.data.primitives import (
    CATEGORIES,
    DOMAIN_KEYS,
    PRIMITIVE_BY_ID,
    PRIMITIVES,
    PRIMITIVES_BY_CATEGORY,
    FeatureVector,
    get_category,
    get_feature_vector,
    get_impl,
    get_impl_cost,
)

__all__ = [
    # BCM
    "BASE_COMPAT_MATRIX",
    "get_base_compat",
    # Domains
    "BUILT_IN_DOMAINS",
    "BUILT_IN_DOMAIN_BY_ID",
    "BUILT_IN_DOMAIN_IDS",
    "get_built_in_domain",
    "is_built_in",
    # Primitives
    "CATEGORIES",
    "DOMAIN_KEYS",
    "PRIMITIVE_BY_ID",
    "PRIMITIVES",
    "PRIMITIVES_BY_CATEGORY",
    "FeatureVector",
    "get_category",
    "get_feature_vector",
    "get_impl",
    "get_impl_cost",
]
