"""Service layer — pure business logic re-exports."""

from app.services.adapter import build_adapter_log
from app.services.domain_resolver import (
    domain_exists,
    list_all_domain_fvs,
    resolve_domain_fv,
    resolve_domain_impls,
)
from app.services.extractor import extract_skill
from app.services.scorer import cosine_sim, score_skill
from app.services.webhook import deliver_webhook, schedule_webhook

__all__ = [
    "build_adapter_log",
    "cosine_sim",
    "deliver_webhook",
    "domain_exists",
    "extract_skill",
    "list_all_domain_fvs",
    "resolve_domain_fv",
    "resolve_domain_impls",
    "schedule_webhook",
    "score_skill",
]
