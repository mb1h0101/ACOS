"""
Policy model: what a mode allows.

A Policy is what the console sends to agents. It is intentionally simple and
JSON-serialisable. Website rules are teacher-facing URL keywords matched
case-insensitively against the student's current foreground browser host.
Teachers may type a simple word such as "google" or paste a URL; pasted URLs
are reduced to their host automatically. App matching is case-insensitive
substring matching against the foreground app name.

Enforcement semantics per mode are decided ENTIRELY console-side and shipped
to the agent, so classroom behaviour is auditable and changeable without
touching agent code.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List


@dataclass
class Policy:
    mode: str
    # website control
    site_mode: str = "off"           # "off" | "allowlist" | "blocklist"
    site_allow: List[str] = field(default_factory=list)
    site_block: List[str] = field(default_factory=list)
    # app control
    app_mode: str = "off"            # "off" | "allowlist" | "blocklist"
    app_allow: List[str] = field(default_factory=list)
    app_block: List[str] = field(default_factory=list)
    # environment
    fullscreen: bool = False         # lock student into fullscreen learning env
    kill_blocked_apps: bool = False  # soft-terminate a blocked app if it comes to front

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> "Policy":
        return Policy(**{k: d.get(k, getattr(Policy, k, None)) for k in
                         ["mode", "site_mode", "site_allow", "site_block",
                          "app_mode", "app_allow", "app_block",
                          "fullscreen", "kill_blocked_apps"]})


def _site_keyword(value: str) -> str:
    """Normalize teacher input into a simple host/URL keyword.

    Examples:
      google                              -> google
      google.com                          -> google.com
      https://classroom.google.com/u/0/h  -> classroom.google.com
    """
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" in value:
        try:
            from urllib.parse import urlparse
            value = (urlparse(value).hostname or value).lower()
        except Exception:
            pass
    value = value.split("/")[0].split("?")[0].split("#")[0]
    return value.strip().strip(".")


def _site_matches(host: str, rule: str) -> bool:
    """Human-friendly but deterministic foreground-site matching.

    - A plain word such as "google" matches an exact hostname label:
      www.google.com, classroom.google.com, accounts.google.com.
      It does NOT match unrelated strings such as notgoogle.example.
    - A host/URL such as classroom.google.com matches that host and its
      subdomains only.
    This keeps the teacher out of DNS/CDN/API details because ACOS evaluates
    only the foreground page the student is actually viewing.
    """
    host = (host or "").lower().strip().strip(".")
    rule = _site_keyword(rule)
    if not host or not rule:
        return False
    if "." in rule:
        return host == rule or host.endswith("." + rule)
    return rule in [x for x in host.split(".") if x]


def site_allowed(host: str, pol: Policy) -> bool:
    """Evaluate only the student's CURRENT foreground browser host."""
    host = (host or "").lower().strip().strip(".")
    if pol.site_mode == "off":
        return True

    values = pol.site_allow if pol.site_mode == "allowlist" else pol.site_block
    matched = any(_site_matches(host, value) for value in values)

    if pol.site_mode == "allowlist":
        return matched
    if pol.site_mode == "blocklist":
        return not matched
    return True


def app_allowed(app: str, pol: Policy) -> bool:
    app = (app or "").lower().strip()
    if pol.app_mode == "off":
        return True
    if pol.app_mode == "allowlist":
        return any(a.lower() in app or app in a.lower() for a in pol.app_allow)
    if pol.app_mode == "blocklist":
        return not any(a.lower() in app for a in pol.app_block)
    return True


# Sensible defaults so the console is usable out of the box.
def default_policies() -> Dict[str, Policy]:
    from common import protocol as P
    return {
        P.MODE_DEMO: Policy(mode=P.MODE_DEMO, fullscreen=True),
        P.MODE_EXERCISE: Policy(
            mode=P.MODE_EXERCISE,
            # A teacher explicitly sets the resources for each lesson in the
            # Console. Empty lists mean "not configured yet", not a surprise
            # hard-coded curriculum.
            site_mode="off", site_allow=[],
            app_mode="off", app_allow=[],
            fullscreen=False, kill_blocked_apps=False),
        P.MODE_REWARD: Policy(
            mode=P.MODE_REWARD, site_mode="off", app_mode="off",
            fullscreen=False),
        P.MODE_FREE: Policy(mode=P.MODE_FREE),
    }
