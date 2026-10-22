from autarkia.tools import RolePolicyResolver, RoleToolPolicy, ToolCatalog, ToolDeclaration


def _catalog():
    catalog = ToolCatalog()
    catalog.declare("echo", ToolDeclaration(domain="utility"))
    catalog.declare("time", ToolDeclaration(domain="utility"))
    catalog.declare("calculator", ToolDeclaration(domain="utility"))
    catalog.declare("get_weather", ToolDeclaration(domain="information"))
    catalog.declare("web_search", ToolDeclaration(domain="information"))
    catalog.declare("run_code", ToolDeclaration(domain="execution"))
    catalog.declare("focus_timer", ToolDeclaration(domain="study"))
    return catalog

PROFILES = {
    "defaults": {"resident": ["time"], "on_demand": ["domain:utility"], "disabled": ["run_code"]},
    "roles": {
        "librarian": {"resident": ["echo"], "disabled": ["web_search"]},
    },
    "modes": {
        "study": {"resident": ["focus_timer"]},
    },
    "routes": [
        {"keywords": ["repeat"], "tools": ["echo", "time"]},
        {"keywords": ["weather"], "tools": ["get_weather"]},
    ],
}


def test_allows_resident_and_on_demand():
    policy = RoleToolPolicy("r", resident=("echo",), on_demand=("time",), disabled=())
    assert policy.allows("echo") is True
    assert policy.allows("time") is True
    assert policy.allows("run_code") is False


def test_disabled_wins_over_on_demand():
    policy = RoleToolPolicy("r", resident=(), on_demand=("echo",), disabled=("echo",))
    assert policy.allows("echo") is False


def test_wildcard_and_domain_selectors():
    policy = RoleToolPolicy("r", resident=(), on_demand=("domain:utility",), disabled=())

    def domain_of(name):
        return "utility" if name in {"echo", "calculator"} else "device"

    assert policy.allows("echo", domain_of=domain_of) is True
    assert policy.allows("camera", domain_of=domain_of) is False
    # Without a resolver, domain: selectors simply never match.
    assert policy.allows("echo") is False


def test_resolver_merges_defaults_role_and_mode():
    resolver = RolePolicyResolver(PROFILES)
    policy = resolver.resolve("librarian")
    assert policy.scope == "librarian"
    assert "echo" in policy.resident
    # A role that declares its own resident list overrides the defaults one.
    assert "time" not in policy.resident
    assert policy.on_demand == ("domain:utility",)  # inherited from defaults
    assert "web_search" in policy.disabled  # role
    assert "run_code" in policy.disabled    # defaults


def test_resolver_defaults_apply_when_role_declares_nothing():
    resolver = RolePolicyResolver(PROFILES)
    policy = resolver.resolve("ghost")
    assert "time" in policy.resident  # defaults
    assert "run_code" in policy.disabled


def test_resolver_mode_overlay_adds_resident():
    resolver = RolePolicyResolver(PROFILES)
    policy = resolver.resolve("librarian", mode="study")
    assert "focus_timer" in policy.resident
    assert "echo" in policy.resident


def test_resolver_unknown_scope_falls_back_to_defaults():
    resolver = RolePolicyResolver(PROFILES)
    policy = resolver.resolve("nobody")
    assert policy.resident == ("time",)
    assert policy.disabled == ("run_code",)


def test_select_resident_plus_keyword_routes():
    resolver = RolePolicyResolver(PROFILES, catalog=_catalog())
    picked = resolver.select("please repeat this for me", scope="librarian")
    assert "echo" in picked
    assert "time" in picked            # keyword route hit, on_demand via domain:utility
    assert "web_search" not in picked  # disabled for librarian


def test_select_dedupes_and_respects_policy():
    resolver = RolePolicyResolver(PROFILES, catalog=_catalog())
    picked = resolver.select("repeat repeat", scope="nobody")
    # "repeat" route hits echo+time; time is resident, echo arrives as
    # on_demand via domain:utility — both allowed, deduped.
    assert picked == ["time", "echo"]


def test_select_without_catalog_drops_domain_on_demand():
    # Without a catalog, "domain:utility" selectors never match, so only
    # resident tools and exact-name routes survive.
    resolver = RolePolicyResolver(PROFILES)
    picked = resolver.select("please repeat this", scope="librarian")
    assert picked == ["echo"]


def test_select_include_filter():
    resolver = RolePolicyResolver(PROFILES)
    picked = resolver.select("repeat", scope="librarian", include=["echo"])
    assert picked == ["echo"]
