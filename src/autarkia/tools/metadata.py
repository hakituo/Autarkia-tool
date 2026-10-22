"""Tool discovery metadata with declared risk levels.

Ported from the Autarkia runtime. The runtime's hard-coded catalog of ~90
concrete tools became a declarative API: each deployment declares what its
tools are, and undeclared tools stay invisible to discovery.

Design rule kept from the original: **risk is never inferred**. A tool
without an explicit ``ToolDeclaration`` gets no metadata, appears in no
search results, and is therefore never advertised to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

# Risk classes, from least to most dangerous. Governance code may rely on
# this ordering; custom levels outside these values are rejected.
RISK_LEVELS: Tuple[str, ...] = (
    "read",
    "write",
    "external_write",
    "device_read",
    "device_control",
    "sensitive",
)

# Load policies: base = always offered, on_demand = found via discovery,
# hidden = exists but never advertised.
LOAD_POLICIES: Tuple[str, ...] = ("base", "on_demand", "hidden")


@dataclass(frozen=True)
class ToolDiscoveryMetadata:
    """Stable metadata used by tool discovery and on-demand loading."""

    name: str
    domain: str
    tags: Tuple[str, ...]
    risk_level: str
    load_policy: str
    short_description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "tags": list(self.tags),
            "risk_level": self.risk_level,
            "load_policy": self.load_policy,
            "short_description": self.short_description,
        }


@dataclass(frozen=True)
class ToolDeclaration:
    """Explicit declaration of a tool's discovery and governance facts."""

    domain: str
    risk_level: str = "read"
    load_policy: str = "on_demand"
    tags: Tuple[str, ...] = field(default_factory=tuple)
    short_description: str = ""

    def __post_init__(self) -> None:
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(
                f"unknown risk_level {self.risk_level!r}; expected one of {RISK_LEVELS}"
            )
        if self.load_policy not in LOAD_POLICIES:
            raise ValueError(
                f"unknown load_policy {self.load_policy!r}; expected one of {LOAD_POLICIES}"
            )


class ToolCatalog:
    """Declares and serves discovery metadata for a set of tool names."""

    def __init__(self) -> None:
        self._declarations: Dict[str, ToolDeclaration] = {}

    def declare(self, name: str, declaration: ToolDeclaration) -> None:
        """Register a declaration; re-declaring the same name replaces it."""
        key = str(name).strip()
        if not key:
            raise ValueError("tool name must be a non-empty string")
        self._declarations[key] = declaration

    def declare_many(
        self, declarations: Mapping[str, ToolDeclaration]
    ) -> None:
        for name, declaration in declarations.items():
            self.declare(name, declaration)

    def has(self, name: str) -> bool:
        return str(name).strip() in self._declarations

    def names(self) -> Tuple[str, ...]:
        return tuple(self._declarations)

    def domain_of(self, name: str) -> str:
        declaration = self._declarations.get(str(name).strip())
        return declaration.domain if declaration else ""

    def get(self, name: str) -> Optional[ToolDeclaration]:
        return self._declarations.get(str(name).strip())

    def build(self, tool: Any) -> Optional[ToolDiscoveryMetadata]:
        """Build discovery metadata for a tool; None when undeclared."""
        name = str(getattr(tool, "name", "") or "")
        declaration = self._declarations.get(name)
        if declaration is None:
            return None
        return ToolDiscoveryMetadata(
            name=name,
            domain=declaration.domain,
            tags=tuple(declaration.tags),
            risk_level=declaration.risk_level,
            load_policy=declaration.load_policy,
            short_description=_compact_description(tool, declaration.short_description),
        )


def _compact_description(tool: Any, override: str = "") -> str:
    raw = str(
        override
        or getattr(tool, "short_description", "")
        or getattr(tool, "description", "")
        or getattr(tool, "name", "")
    ).strip()
    first_line = raw.splitlines()[0].strip() if raw else ""
    summary = re.split(r"[。.!?！？]", first_line, maxsplit=1)[0].strip()
    if len(summary) > 60:
        return summary[:57] + "..."
    return summary


def search_tool_metadata(
    metadata_items: Iterable[ToolDiscoveryMetadata],
    query: str,
    *,
    limit: int = 5,
) -> List[ToolDiscoveryMetadata]:
    """Lightweight CJK/English mixed retrieval with stable ordering.

    Scoring favors exact name matches, then name/description/tag hits;
    CJK queries are additionally matched by character bigrams. Pure
    heuristics — no embedding dependency.
    """
    normalized = str(query or "").strip().lower()
    if not normalized:
        return []
    english_terms = re.findall(r"[a-z0-9_]+", normalized)
    query_cjk_bigrams = {
        chunk[index:index + 2]
        for chunk in re.findall(r"[\u4e00-\u9fff]+", normalized)
        for index in range(max(0, len(chunk) - 1))
    }
    scored: List[Tuple[int, int, ToolDiscoveryMetadata]] = []
    for index, item in enumerate(metadata_items):
        score = 0
        name = item.name.lower()
        description = item.short_description.lower()
        if normalized == name:
            score += 300
        if normalized in name or name in normalized:
            score += 120
        if normalized in description or description in normalized:
            score += 100
        for tag in item.tags:
            normalized_tag = tag.lower()
            if normalized_tag and normalized_tag in normalized:
                score += 45
        if item.domain.lower() in normalized:
            score += 55
        candidate_text = " ".join((description, *item.tags))
        candidate_cjk_bigrams = {
            chunk[index:index + 2]
            for chunk in re.findall(r"[\u4e00-\u9fff]+", candidate_text)
            for index in range(max(0, len(chunk) - 1))
        }
        score += 12 * len(query_cjk_bigrams & candidate_cjk_bigrams)
        for term in english_terms:
            if len(term) < 2:
                continue
            if term in name:
                score += 25
            if term in description:
                score += 15
            if any(term in tag.lower() for tag in item.tags):
                score += 10
        if score > 0:
            scored.append((score, -index, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    bounded_limit = max(1, min(int(limit or 5), 8))
    return [row[2] for row in scored[:bounded_limit]]
