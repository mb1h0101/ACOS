"""
Teacher Console discovery for Student Agents.

Three tiers, tried in order by the agent:

  1. Manual override   - ACOS_CONSOLE=host:port env var or a config file.
                         Always wins; used for locked-down school networks.
  2. mDNS / Bonjour    - console advertises _acos._tcp; agent browses.
  3. UDP beacon        - console broadcasts a beacon on BEACON_PORT; agent
                         listens. Survives networks where mDNS is filtered
                         but broadcast is allowed.

The console advertises via ALL available tiers simultaneously so an agent
can find it however the network is configured.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from typing import Optional, Tuple

from . import protocol as P

try:  # zeroconf is optional; agent still works via beacon/manual without it
    from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser
    _HAVE_ZC = True
except Exception:  # pragma: no cover
    _HAVE_ZC = False


def _primary_ip() -> str:
    """Best-effort primary LAN IP (no traffic actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Console side: advertise
# ---------------------------------------------------------------------------
class ConsoleAdvertiser:
    def __init__(self, port: int, ip: Optional[str] = None):
        self.port = port
        self.ip = ip or _primary_ip()
        self._zc = None
        self._info = None
        self._beacon_stop = threading.Event()
        self._beacon_thread = None

    def start(self):
        if _HAVE_ZC:
            try:
                self._zc = Zeroconf()
                self._info = ServiceInfo(
                    P.SERVICE_TYPE,
                    f"{P.SERVICE_NAME}.{P.SERVICE_TYPE}",
                    addresses=[socket.inet_aton(self.ip)],
                    port=self.port,
                    properties={"v": str(P.PROTOCOL_VERSION)},
                )
                self._zc.register_service(self._info)
            except Exception:
                self._zc = None
        self._beacon_thread = threading.Thread(
            target=self._beacon_loop, daemon=True)
        self._beacon_thread.start()

    def _beacon_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = P.BEACON_MAGIC + b"|" + json.dumps(
            {"ip": self.ip, "port": self.port, "v": P.PROTOCOL_VERSION}
        ).encode()
        while not self._beacon_stop.is_set():
            try:
                sock.sendto(payload, ("255.255.255.255", P.BEACON_PORT))
            except Exception:
                pass
            self._beacon_stop.wait(2.0)
        sock.close()

    def stop(self):
        self._beacon_stop.set()
        if self._zc and self._info:
            try:
                self._zc.unregister_service(self._info)
                self._zc.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Agent side: find the console
# ---------------------------------------------------------------------------
def _manual_override() -> Optional[Tuple[str, int]]:
    v = os.environ.get("ACOS_CONSOLE")
    if not v:
        # config file dropped next to the agent by INSTALL.command (optional)
        cfg = os.path.expanduser("~/Library/Application Support/ACOS/console.txt")
        if os.path.exists(cfg):
            try:
                v = open(cfg).read().strip()
            except Exception:
                v = None
    if not v:
        return None
    try:
        host, port = v.rsplit(":", 1)
        return host, int(port)
    except Exception:
        return None


def _find_via_beacon(timeout: float) -> Optional[Tuple[str, int]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", P.BEACON_PORT))
    except Exception:
        return None
    sock.settimeout(timeout)
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                return None
            if data.startswith(P.BEACON_MAGIC + b"|"):
                try:
                    info = json.loads(data.split(b"|", 1)[1])
                    return info["ip"], int(info["port"])
                except Exception:
                    continue
    finally:
        sock.close()
    return None


def _find_via_mdns(timeout: float) -> Optional[Tuple[str, int]]:
    if not _HAVE_ZC:
        return None
    found = {}

    class _L:
        def add_service(self, zc, type_, name):
            try:
                info = zc.get_service_info(type_, name, timeout=int(timeout * 1000))
                if info and info.addresses:
                    found["addr"] = (socket.inet_ntoa(info.addresses[0]), info.port)
            except Exception:
                pass
        def update_service(self, *a):
            pass
        def remove_service(self, *a):
            pass

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, P.SERVICE_TYPE, _L())
        deadline = time.time() + timeout
        while time.time() < deadline and "addr" not in found:
            time.sleep(0.1)
    finally:
        zc.close()
    return found.get("addr")


def discover(total_timeout: float = 8.0) -> Optional[Tuple[str, int]]:
    """Return (host, port) of the console, or None. Tries all tiers."""
    m = _manual_override()
    if m:
        return m
    r = _find_via_mdns(min(4.0, total_timeout))
    if r:
        return r
    return _find_via_beacon(min(4.0, total_timeout))
