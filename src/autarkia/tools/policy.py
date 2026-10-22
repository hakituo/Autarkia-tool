"""Role tool policies: resident / on-demand / disabled per role.

Ported from the Autarkia runtime. The host's YAML config lookup became an
injected ``profiles`` mapping so any deployment can source the data from
YAML, TOML, a database, or plain dicts.

Profile structure::

    {
        "defaults": {"resident": [...], "on_demand": [...], "disabled": [...]},
        "roles":   {"<scope>": {"resident": [...], "on_demand": [...], "disabled": [...]}},
        "modes":   {"<mode>": {"resident": [...], "on_demand": [...], "disabled": [...]}},
        "routes":  [{"keywords": [...], "tools": [...]}],
    }

Selector syntax inside those lists: an exact tool name, ``*`` (wildcard),
or ``domain:<name>`` (every tool declared in that domain).
"""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Mapping, Optional, Tuple

from autarkia.tools.metadata import ToolCatalog


def _matches(
    name: str,
    selectors: Tuple[str, ...],
    domain_of: Optional[Callable[[str], str]] = None,
) -> bool:
    if name in selectors or "*" in selectors:
        return True
    if domain_of is not None:
        return f"domain:{domain_of(name)}" in selectors
    return False


@dataclass(frozen=True)
class RoleToolPolicy:
    """Immutable per-role view of what tools may appear and run."""

    scope: str
    resident: Tuple[str, ...]
    on_demand: Tuple[str, ...]
    disabled: Tuple[str, ...]

    def allows(
        self,
        name: str,
        *,
        domain_of: Optional[Callable[[str], str]] = None,
    ) -> bool:
        """A tool is allowed unless disabled, and resident or on-demand.

        ``domain_of`` enables ``domain:`` selectors; without it only exact
        names and ``*`` are honored. Disabled always wins.
        """
        if _matches(name, self.disabled, domain_of):
            return False
        return name in self.resident or _matches(name, self.on_demand, domain_of)


class RolePolicyResolver:
    """Resolves :class:`RoleToolPolicy` instances from an injected profile mapping."""

    def __init__(
        self,
        profiles: Mapping,
        catalog: Optional[ToolCatalog] = None,
    ) -> None:
        self._profiles = profiles
        self._catalog = catalog

    def _domain_of(self, name: str) -> str:
        return self._catalog.domain_of(name) if self._catalog else ""

    def resolve(self, scope: str = "", *, mode: str = "chat") -> RoleToolPolicy:
        data = self._profiles
        defaults = data.get("defaults", {}) or {}
        role = (data.get("roles", {}) or {}).get(scope, {}) or {}
        mode_config = (data.get("modes", {}) or {}).get(mode, {}) or {}
        resident = tuple(
            dict.fromkeys(
                list(role.get("resident", defaults.get("resident", [])))
                + list(mode_config.get("resident", []))
            )
        )
        on_demand = tuple(
            dict.fromkeys(
                list(mode_config.get("on_demand", []))
                or list(role.get("on_demand", defaults.get("on_demand", [])))
            )
        )
        disabled = tuple(
            dict.fromkeys(
                list(defaults.get("disabled", []))
                + list(role.get("disabled", []))
                + list(mode_config.get("disabled", []))
            )
        )
        return RolePolicy(scope, resident, on_demand, disabled)

    def select(
        self,
        message: str,
        *,
        scope: str = "",
        mode: str = "chat",
        include: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """First-turn selection: resident tools plus keyword-route hits.

        The result is a candidate list only — visibility filtering and the
        execution guard still apply downstream.
        """
        policy = self.resolve(scope, mode=mode)
        domain_of = self._domain_of
        selected = [name for name in policy.resident if policy.allows(name, domain_of=domain_of)]
        lower = str(message or "").lower()
        for route in self._profiles.get("routes", []) or []:
            if any(str(keyword).lower() in lower for keyword in route.get("keywords", [])):
                selected.extend(route.get("tools", []))
        picked = [name for name in dict.fromkeys(selected) if policy.allows(name, domain_of=domain_of)]
        if include is not None:
            allowed = set(include)
            picked = [name for name in picked if name in allowed]
        return picked


# Kept for a friendlier error message when callers use the old name.
RolePolicy = RoleToolPolicy
