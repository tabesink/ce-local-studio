from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.dev.seed_gate import require_seed_reset_allowed, require_seed_writes_allowed
from context_engine.models import (
    PROMPT_TEMPLATE_STATE_APPROVED,
    PROMPT_TEMPLATE_STATE_DISABLED,
    PromptTemplate,
)

FIXTURE_TEMPLATE_SAFETY_SUMMARY = "template_safety_summary"
FIXTURE_TEMPLATE_DISABLED = "template_disabled"

TEMPLATE_SAFETY_SUMMARY_ID = "c0ffee01-0001-4001-8001-000000000001"
TEMPLATE_DISABLED_ID = "c0ffee01-0001-4001-8001-000000000002"


@dataclass(frozen=True)
class PromptTemplateFixture:
    fixture_key: str
    seed_id: str
    name: str
    description: str
    body: str
    state: str


PROMPT_TEMPLATE_FIXTURES = (
    PromptTemplateFixture(
        fixture_key=FIXTURE_TEMPLATE_SAFETY_SUMMARY,
        seed_id=TEMPLATE_SAFETY_SUMMARY_ID,
        name="Safety summary",
        description="Summarize only authorized safety-critical guidance.",
        body=(
            "Summarize only the authorized context. Prefer concrete safety steps. "
            "Do not invent missing procedures or general knowledge."
        ),
        state=PROMPT_TEMPLATE_STATE_APPROVED,
    ),
    PromptTemplateFixture(
        fixture_key=FIXTURE_TEMPLATE_DISABLED,
        seed_id=TEMPLATE_DISABLED_ID,
        name="Disabled template",
        description="Disabled fixture used to reject target-state references.",
        body="This template is disabled and must not be accepted for assembly.",
        state=PROMPT_TEMPLATE_STATE_DISABLED,
    ),
)

FIXTURE_TEMPLATE_IDS = frozenset(entry.seed_id for entry in PROMPT_TEMPLATE_FIXTURES)


def seed_prompt_template_fixtures(
    db: Session,
    *,
    reset: bool = False,
    environment: str | None = None,
    allow_test_seed: str | None = None,
) -> None:
    require_seed_writes_allowed(environment=environment, allow_test_seed=allow_test_seed)
    if reset:
        require_seed_reset_allowed(environment=environment)
    existing_by_id = {template.id: template for template in db.scalars(select(PromptTemplate))}
    for entry in PROMPT_TEMPLATE_FIXTURES:
        template = existing_by_id.get(entry.seed_id)
        if template is None:
            db.add(
                PromptTemplate(
                    id=entry.seed_id,
                    name=entry.name,
                    description=entry.description,
                    body=entry.body,
                    state=entry.state,
                )
            )
            continue
        changed = False
        for attr, value in (
            ("name", entry.name),
            ("description", entry.description),
            ("body", entry.body),
            ("state", entry.state),
        ):
            if getattr(template, attr) != value:
                setattr(template, attr, value)
                changed = True
        if changed:
            template.updated_at = utc_now()
    if reset:
        for template in list(existing_by_id.values()):
            if template.id not in FIXTURE_TEMPLATE_IDS:
                db.delete(template)
    db.commit()
