"""
ACOS wire protocol.

All messages are JSON objects with at least:
    { "v": PROTOCOL_VERSION, "type": "<msg-type>", "ts": <epoch_ms>, ... }

Transport is WebSocket. The Teacher Console is the SERVER; every Student
Agent is a CLIENT that dials out to the console (agents never listen for
inbound connections, which keeps them firewall-friendly and avoids opening
ports on student machines).

This module is the single source of truth for the protocol and is shared
verbatim by both the console and the agent. Keep it dependency-free
(stdlib only) so it bundles cleanly into the packaged agent.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict

PROTOCOL_VERSION = 1

# mDNS / Bonjour service used for discovery.
SERVICE_TYPE = "_acos._tcp.local."
SERVICE_NAME = "ACOS Teacher Console"

# UDP beacon fallback (used when mDNS is blocked on the school network).
BEACON_PORT = 47800
BEACON_MAGIC = b"ACOS-BEACON-1"

# ---------------------------------------------------------------------------
# Modes (mutually exclusive learning states)
# ---------------------------------------------------------------------------
MODE_DEMO = "DEMO"        # Teacher demonstrating; student screen locked to broadcast
MODE_EXERCISE = "EXERCISE"  # Students work; only allowlisted sites/apps permitted
MODE_REWARD = "REWARD"    # Temporary relaxed policy, countdown, auto-return to EXERCISE
MODE_FREE = "FREE"        # No restrictions (e.g. break)
MODES = {MODE_DEMO, MODE_EXERCISE, MODE_REWARD, MODE_FREE}

# ---------------------------------------------------------------------------
# Overlays (transient states layered on top of a mode)
# ---------------------------------------------------------------------------
OVERLAY_NONE = "NONE"
OVERLAY_BLACKOUT = "BLACKOUT"      # Full black screen + "eyes on teacher" message
OVERLAY_FOCUS_NOW = "FOCUS_NOW"    # Snap all apps closed / bring learning env to front
OVERLAY_BROADCAST = "BROADCAST"    # Teacher screen shown fullscreen on student

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------
# Agent -> Console
T_HELLO = "hello"                  # agent announces itself on connect
T_HEARTBEAT = "heartbeat"          # periodic liveness
T_EVENT = "event"                  # anonymous analytics event
T_THUMBNAIL = "thumbnail"          # base64 jpeg of student screen
T_STATE = "state"                  # agent reports its current applied state
T_ACK = "ack"                      # acknowledge a command (for latency measurement)

# Console -> Agent
T_WELCOME = "welcome"              # console accepts agent, returns assigned info
T_SET_MODE = "set_mode"           # switch learning mode
T_SET_OVERLAY = "set_overlay"     # apply/clear an overlay
T_SET_POLICY = "set_policy"       # website/app allow/block policy
T_REQUEST_THUMB = "request_thumb"  # ask for a fresh thumbnail
T_BROADCAST_FRAME = "broadcast_frame"  # a frame of the teacher's screen
T_PING = "ping"                   # latency probe
T_EMERGENCY_FOCUS = "emergency_focus"  # hard reset to EXERCISE + clear overlays


def now_ms() -> int:
    return int(time.time() * 1000)


def new_session_id() -> str:
    """Anonymous per-agent-boot session id. Never derived from user identity."""
    return "s-" + uuid.uuid4().hex[:16]


def msg(type_: str, **fields: Any) -> Dict[str, Any]:
    m = {"v": PROTOCOL_VERSION, "type": type_, "ts": now_ms()}
    m.update(fields)
    return m


def validate(m: Dict[str, Any]) -> bool:
    """Cheap structural validation; drops malformed frames rather than crash."""
    if not isinstance(m, dict):
        return False
    if m.get("v") != PROTOCOL_VERSION:
        return False
    if not isinstance(m.get("type"), str):
        return False
    return True
