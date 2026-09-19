import argparse
import asyncio

from sqlalchemy import select

from api.db import build_engine, build_session_factory
from api.models import Lead, Organization


async def run(org_slug: str, limit: int) -> None:
    engine = build_engine()
    try:
        async with build_session_factory(engine)() as session:
            org = await session.scalar(
                select(Organization).where(Organization.slug == org_slug)
            )
            if org is None:
                raise SystemExit(f"Organization '{org_slug}' not found")
            leads = (
                await session.scalars(
                    select(Lead)
                    .where(Lead.organization_id == org.id)
                    .order_by(Lead.created_at.desc())
                    .limit(limit)
                )
            ).all()
    finally:
        await engine.dispose()

    if not leads:
        print("No leads yet.")
        return

    for lead in leads:
        print(
            f"{lead.created_at:%Y-%m-%d %H:%M}  {lead.name} <{lead.email}>  "
            f"company={lead.company or '-'}  team={lead.team_size or '-'}  status={lead.status}"
        )
        if lead.need:
            print(f"    need: {lead.need}")
        print(f'    consent: "{lead.consent_reply}" after "{lead.consent_prompt[:100]}"')


def main() -> None:
    parser = argparse.ArgumentParser(description="List captured leads for one company.")
    parser.add_argument("--org", default="nimbus-crm-demo")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(args.org, args.limit))


if __name__ == "__main__":
    main()