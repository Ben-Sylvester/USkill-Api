from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import AuthContext, get_auth
from app.data import PRIMITIVES, PRIMITIVE_BY_ID, PRIMITIVES_BY_CATEGORY, CATEGORIES

router = APIRouter(prefix="/primitives", tags=["Primitives"])


@router.get("")
async def list_primitives(
    request: Request,
    category: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth),
):
    rid = request.state.request_id
    if category:
        cat = category.upper()
        if cat not in CATEGORIES:
            raise HTTPException(422, {"error": "INVALID_REQUEST", "message": f"Unknown category '{category}'. Valid: {', '.join(CATEGORIES)}", "request_id": rid})
        items = PRIMITIVES_BY_CATEGORY[cat]
    else:
        items = PRIMITIVES

    return {
        "primitives": [
            {
                "id": p["id"],
                "name": p["name"],
                "category": p["category"],
                "desc": p["desc"],
                "complexity": p["complexity"],
                "reversible": p["reversible"],
                "features": p["features"],
            }
            for p in items
        ],
        "total": len(items),
        "categories": CATEGORIES,
        "request_id": rid,
    }


@router.get("/{primitive_id}")
async def get_primitive(
    primitive_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
):
    rid = request.state.request_id
    p = PRIMITIVE_BY_ID.get(primitive_id)
    if p is None:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": f"Unknown primitive '{primitive_id}'.", "request_id": rid})
    return {**p, "request_id": rid}
