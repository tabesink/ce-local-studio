from __future__ import annotations

from typing import Any

from context_engine.models import PromptTemplate


def safe_prompt_template_ref(template: PromptTemplate) -> dict[str, Any]:
    return {
        "kind": "template",
        "label": template.name,
        "description": template.description,
    }
