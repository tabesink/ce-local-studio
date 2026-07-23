from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.models import PROMPT_TEMPLATE_STATE_APPROVED, PromptTemplate


@dataclass(frozen=True)
class PromptTemplateSeed:
    seed_id: str
    name: str
    description: str
    body: str


PROMPT_TEMPLATE_CATALOG = (
    PromptTemplateSeed(
        seed_id="11111111-1111-4111-8111-111111111111",
        name="Concise synthesis",
        description="Answer directly with only the necessary caveats.",
        body="Answer the member directly and concisely. Use provided context only when it is relevant.",
    ),
    PromptTemplateSeed(
        seed_id="22222222-2222-4222-8222-222222222222",
        name="Decision brief",
        description="Frame tradeoffs, recommendation, and next action.",
        body=(
            "Produce a decision brief with the recommendation first, then material tradeoffs, "
            "risks, and the next concrete action."
        ),
    ),
    PromptTemplateSeed(
        seed_id="33333333-3333-4333-8333-333333333333",
        name="Evidence audit",
        description="Separate supported claims from unknowns.",
        body=(
            "Separate claims supported by the provided context from assumptions or unknowns. "
            "Do not invent missing facts."
        ),
    ),
)


def seed_prompt_templates(db: Session) -> None:
    existing_by_id = {template.id: template for template in db.scalars(select(PromptTemplate))}
    for entry in PROMPT_TEMPLATE_CATALOG:
        template = existing_by_id.get(entry.seed_id)
        if template is None:
            db.add(
                PromptTemplate(
                    id=entry.seed_id,
                    name=entry.name,
                    description=entry.description,
                    body=entry.body,
                    state=PROMPT_TEMPLATE_STATE_APPROVED,
                )
            )
            continue
        changed = False
        for attr, value in (
            ("name", entry.name),
            ("description", entry.description),
            ("body", entry.body),
            ("state", PROMPT_TEMPLATE_STATE_APPROVED),
        ):
            if getattr(template, attr) != value:
                setattr(template, attr, value)
                changed = True
        if changed:
            template.updated_at = utc_now()
    db.commit()


def safe_prompt_template_ref(template: PromptTemplate) -> dict[str, Any]:
    return {
        "kind": "template",
        "label": template.name,
        "description": template.description,
    }
