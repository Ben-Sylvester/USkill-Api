#!/usr/bin/env python3
"""
Seed an API key into the database.

Usage:
    python scripts/seed_api_key.py \
        --org-id  "org_acme_123" \
        --name    "Acme Production Key" \
        --plan    pro \
        --prefix  usk_prod_

    # Or for a read-only key:
    python scripts/seed_api_key.py \
        --org-id  "org_acme_123" \
        --name    "Acme Read-Only Key" \
        --plan    pro \
        --prefix  usk_ro_
"""

import argparse
import asyncio
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from passlib.context import CryptContext

from app.config import get_settings
from app.models.api_key import ApiKey

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_key(
    org_id: str,
    name: str,
    plan: str,
    prefix: str,
    scopes: str,
    db_url: str,
) -> str:
    raw_key = prefix + secrets.token_hex(16)
    key_hash = _pwd_ctx.hash(raw_key)
    key_id = "key_" + secrets.token_hex(5)
    key_prefix_stored = raw_key[:12]

    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        key = ApiKey(
            id=key_id,
            org_id=org_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix_stored,
            plan=plan,
            is_active=True,
            scopes=scopes,
            created_at=datetime.now(timezone.utc),
        )
        session.add(key)
        await session.commit()

    await engine.dispose()
    return raw_key


def main():
    parser = argparse.ArgumentParser(description="Seed a USKill API key")
    parser.add_argument("--org-id",  required=True,  help="Organisation ID")
    parser.add_argument("--name",    required=True,  help="Human-readable key name")
    parser.add_argument("--plan",    default="free",  choices=["free", "pro", "enterprise"])
    parser.add_argument("--prefix",  default="usk_prod_",
                        choices=["usk_prod_", "usk_test_", "usk_ro_"])
    parser.add_argument("--scopes",  default="read write")
    parser.add_argument("--db-url",  default=None,
                        help="Override DATABASE_URL from env")

    args = parser.parse_args()

    settings = get_settings()
    db_url = args.db_url or settings.database_url

    print(f"\n⚙  Seeding API key for org '{args.org_id}'...")
    raw = asyncio.run(seed_key(
        org_id=args.org_id,
        name=args.name,
        plan=args.plan,
        prefix=args.prefix,
        scopes=args.scopes,
        db_url=db_url,
    ))

    print(f"""
╔══════════════════════════════════════════════════════╗
║  API Key Created — SAVE THIS, IT WON'T BE SHOWN AGAIN
╠══════════════════════════════════════════════════════╣
║  Key:   {raw}
║  Org:   {args.org_id}
║  Plan:  {args.plan}
║  Scope: {args.scopes}
╚══════════════════════════════════════════════════════╝

Add to Authorization header:
  Authorization: Bearer {raw}
""")


if __name__ == "__main__":
    main()
