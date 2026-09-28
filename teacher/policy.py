"""
Policy model: what a mode allows.

A Policy is what the console sends to agents. It is intentionally simple and
JSON-serialisable. Host matching is suffix-based (so "khanacademy.org" also
matches "www.khanacademy.org"). App matching is by bundle id or app name
(case-insensitive substring).

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


def site_allowed(host: str, pol: Policy) -> bool:
    host = (host or "").lower().strip()
    if pol.site_mode == "off":
        return True
    if pol.site_mode == "allowlist":
        return any(host == h or host.endswith("." + h) or host.endswith(h)
                   for h in (x.lower() for x in pol.site_allow))
    if pol.site_mode == "blocklist":
        return not any(host == h or host.endswith("." + h) or host.endswith(h)
                       for h in (x.lower() for x in pol.site_block))
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
            mode=P.MODE_EXERCISE, site_mode="allowlist",
            site_allow=["khanacademy.org", "wikipedia.org"],
            app_mode="blocklist",
            app_block=["Messages", "Games", "Steam", "Discord"],
            fullscreen=True, kill_blocked_apps=True),
        P.MODE_REWARD: Policy(
            mode=P.MODE_REWARD, site_mode="off", app_mode="off",
            fullscreen=False),
        P.MODE_FREE: Policy(mode=P.MODE_FREE),
    }
