from __future__ import annotations

import re

DOMAIN_REQUIRED_PATTERNS: tuple[str, ...] = (
    r"\bmanual\b",
    r"\bdocument\b",
    r"\bsource\b",
    r"\bprocedure\b",
    r"\bpolicy\b",
    r"\bsop\b",
    r"\baccording to\b",
    r"\bin the (doc|file|pdf|manual)\b",
    r"\bknowledge domain\b",
    r"\bwhat does .+ say\b",
    r"\bsummarize .+ (doc|document|manual|sop|policy)\b",
)

_DOMAIN_REQUIRED_RE = tuple(re.compile(pattern, re.IGNORECASE) for pattern in DOMAIN_REQUIRED_PATTERNS)


def requires_domain(message: str) -> bool:
    return any(pattern.search(message) for pattern in _DOMAIN_REQUIRED_RE)
