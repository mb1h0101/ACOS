"""
Enforcement layer — the part that actually touches the student's Mac.

This module is platform-aware. On macOS it uses ONLY sanctioned OS facilities:
  * `screencapture`            for thumbnails and teacher-broadcast capture
    -> requires the TCC "Screen Recording" permission (manual first grant).
  * AppleScript / `lsappinfo`  to read the frontmost app and, best-effort, the
    frontmost browser tab's host
    -> reading the browser URL requires the TCC "Automation"/"Accessibility"
       permission (manual first grant).
  * NSWorkspace-style app listing via `lsappinfo`, and `osascript`/`kill` to
    soft-terminate a blocked app that the student brings to the front.
  * a fullscreen Tk overlay window for BLACKOUT / broadcast display / kiosk.

HONEST ENFORCEMENT BOUNDARY
---------------------------
Without an MDM profile or a signed NetworkExtension content filter, ACOS
cannot *prevent* a determined student from reaching a site or launching an
app at the packet/exec level. What it does instead ("soft enforcement"):
  - detects a disallowed foreground app / browser host,
  - logs blocked_app / blocked_navigation,
  - raises the BLACKOUT/kiosk overlay and (optionally) terminates the app.
This is effective for ordinary classroom use and is transparent about its
limits. See KNOWN_LIMITATIONS.md. Nothing here bypasses macOS security or
acquires permissions silently.

On non-macOS (the CI/load-test box) every OS call is replaced by a no-op or a
simulated signal so the full agent logic can run and be tested.
"""
from __future__ import annotations

import base64
import ctypes
import os
import platform
import shutil
import subprocess
import tempfile
import time
from typing import Optional, Tuple

IS_MAC = platform.system() == "Darwin"


# ---------------------------------------------------------------------------
# Permission checks (macOS). These check state only; they never try to grant.
# ---------------------------------------------------------------------------
def check_permissions() -> dict:
    """
    Returns {permission: {"granted": bool|None, "how_to": str}}.
    granted is None when we cannot determine it programmatically (common for
    TCC). We NEVER report a permission as granted when we are not sure.
    """
    if not IS_MAC:
        return {
            "screen_recording": {"granted": True, "how_to": "(non-macOS: simulated)"},
            "accessibility": {"granted": True, "how_to": "(non-macOS: simulated)"},
        }
    res = {}
    # Screen Recording: probe by attempting a 1px capture; if the file is all
    # black / fails we treat as not granted. Best-effort — macOS gives no clean
    # API to *query* TCC without triggering the prompt.
    sr = _probe_screen_recording()
    res["screen_recording"] = {
        "granted": sr,
        "how_to": "System Settings > Privacy & Security > Screen Recording > enable ACOS Student Agent",
    }
    # Accessibility / Automation for reading browser URL.
    ax = _probe_accessibility()
    res["accessibility"] = {
        "granted": ax,
        "how_to": "System Settings > Privacy & Security > Accessibility > enable ACOS Student Agent",
    }
    return res


def _screen_recording_granted() -> Optional[bool]:
    """Query macOS Screen Recording TCC state without triggering a prompt.

    CGPreflightScreenCaptureAccess() is the supported non-interactive preflight
    API on macOS 10.15+.  Unlike invoking `screencapture`, it does not request
    permission and therefore cannot create a repeating permission-dialog loop.
    """
    if not IS_MAC:
        return True
    try:
        cg = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        fn = cg.CGPreflightScreenCaptureAccess
        fn.argtypes = []
        fn.restype = ctypes.c_bool
        return bool(fn())
    except Exception:
        # Unknown is safer than probing by taking a screenshot, because the
        # latter can itself trigger TCC prompts repeatedly.
        return None


def _probe_screen_recording() -> Optional[bool]:
    return _screen_recording_granted()


def _probe_accessibility() -> Optional[bool]:
    try:
        # If we can query System Events for the frontmost process, Automation
        # permission is effectively present.
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process whose frontmost is true'],
            timeout=5, capture_output=True, text=True)
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Screen capture -> thumbnail
# ---------------------------------------------------------------------------
def capture_thumbnail_jpeg_b64(max_w: int = 320, quality: int = 40) -> Optional[str]:
    """Capture the primary display and return a small base64 JPEG, or None."""
    if not IS_MAC:
        return _simulated_thumbnail(max_w)

    # Never invoke screencapture when TCC has not granted Screen Recording.
    # Invoking it while denied can cause macOS to show a permission dialog on
    # every thumbnail cycle (the agent pushes every few seconds).
    if _screen_recording_granted() is not True:
        return None

    try:
        fd, raw = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        # -x silent, -t jpg. Scaling done by sips afterwards (ships with macOS).
        subprocess.run(["screencapture", "-x", "-t", "jpg", raw],
                       timeout=6, capture_output=True)
        if not (os.path.exists(raw) and os.path.getsize(raw) > 0):
            return None
        subprocess.run(["sips", "-Z", str(max_w), "-s", "formatOptions",
                        str(quality), raw], timeout=6, capture_output=True)
        with open(raw, "rb") as f:
            b = f.read()
        os.unlink(raw)
        return base64.b64encode(b).decode()
    except Exception:
        return None


def _simulated_thumbnail(max_w: int) -> str:
    """A tiny valid JPEG so the whole pipeline (encode->WS->decode->render) is
    exercised on the load-test box. Not a real screenshot."""
    # 1x1 grey JPEG.
    tiny = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
        "07090908"
        "0a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c283729"
        "2c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc40014"
        "00010000000000000000000000000000000009ffc4001411010000000000000000000"
        "0000000000000ffda0008010100003f00d2cf20ffd9")
    return base64.b64encode(tiny).decode()


# ---------------------------------------------------------------------------
# Foreground app + browser host detection
# ---------------------------------------------------------------------------
def frontmost_app() -> Optional[str]:
    if not IS_MAC:
        return _sim_state.get("app")
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process whose frontmost is true'],
            timeout=4, capture_output=True, text=True)
        return out.stdout.strip() or None
    except Exception:
        return None


def frontmost_browser_host() -> Optional[str]:
    """Best-effort. Returns the host of the active tab in Safari/Chrome, or
    None. Requires Automation permission for the browser."""
    if not IS_MAC:
        url = _sim_state.get("url")
        return _host(url) if url else None
    scripts = [
        'tell application "Google Chrome" to get URL of active tab of front window',
        'tell application "Safari" to get URL of front document',
    ]
    for s in scripts:
        try:
            out = subprocess.run(["osascript", "-e", s], timeout=4,
                                 capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip():
                return _host(out.stdout.strip())
        except Exception:
            continue
    return None


def _host(url: str) -> Optional[str]:
    try:
        from urllib.parse import urlparse
        return (urlparse(url).hostname or "").lower() or None
    except Exception:
        return None


def terminate_app(app_name: str) -> bool:
    """Soft-quit an app in the current user session (no elevated privileges)."""
    if not IS_MAC:
        _sim_state["app"] = "Finder"
        return True
    try:
        subprocess.run(["osascript", "-e", f'tell application "{app_name}" to quit'],
                       timeout=4, capture_output=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Overlay (BLACKOUT / broadcast / kiosk). Real impl uses Tk fullscreen.
# ---------------------------------------------------------------------------
class Overlay:
    """
    Fullscreen borderless window used for BLACKOUT, teacher broadcast display,
    and the FOCUS_NOW kiosk. Uses Tkinter (ships with macOS system Python and
    bundles with PyInstaller). On the load-test box Tk is absent/headless, so
    the overlay degrades to state tracking only — the agent logic is unchanged.
    """
    def __init__(self):
        self._tk = None
        self._root = None
        self._label = None
        self.state = "hidden"
        try:
            import tkinter  # noqa
            self._tk = tkinter
        except Exception:
            self._tk = None

    def _ensure(self):
        if self._tk is None:
            return False
        if self._root is None:
            try:
                self._root = self._tk.Tk()
                self._root.configure(bg="black")
                self._root.attributes("-fullscreen", True)
                try:
                    self._root.attributes("-topmost", True)
                except Exception:
                    pass
                self._label = self._tk.Label(self._root, bg="black", fg="white",
                                             font=("Helvetica", 48))
                self._label.pack(expand=True)
                self._root.withdraw()
            except Exception:
                self._root = None
                return False
        return True

    def blackout(self, message="請看老師這裡"):
        """Teacher attention banner (non-blocking)."""
        self.state = "attention"
        if self._ensure():
            try:
                sw = self._root.winfo_screenwidth()
                h = 150
                self._root.attributes("-fullscreen", False)
                self._root.geometry(f"{sw}x{h}+0+0")
                self._root.configure(bg="#111111")
                self._label.configure(
                    text=f"👀  {message}",
                    image="",
                    bg="#111111",
                    fg="white",
                    font=("Helvetica", 42, "bold"),
                )
                self._root.deiconify()
                self._root.lift()
                self._root.update()
            except Exception:
                pass

    def policy_notice(self, message="此內容目前未開放"):
        """Non-blocking policy notice. It auto-clears when the student returns
        to an allowed resource; unlike teacher attention/focus it must never
        become a sticky classroom state."""
        self.state = "policy_block"
        if self._ensure():
            try:
                sw = self._root.winfo_screenwidth()
                h = 150
                self._root.attributes("-fullscreen", False)
                self._root.geometry(f"{sw}x{h}+0+0")
                self._root.configure(bg="#111111")
                self._label.configure(
                    text=f"⚠  {message}",
                    image="",
                    bg="#111111",
                    fg="white",
                    font=("Helvetica", 34, "bold"),
                )
                self._root.deiconify()
                self._root.lift()
                self._root.update()
            except Exception:
                pass

    def show_broadcast(self, jpeg_b64: str):
        self.state = "broadcast"
        if self._ensure():
            try:
                from tkinter import PhotoImage  # noqa
                # Tk can't decode JPEG natively; a real build ships Pillow.
                # We keep the state contract; rendering handled if Pillow present.
                self._render_image(jpeg_b64)
                self._root.deiconify()
                self._root.update()
            except Exception:
                pass

    def _render_image(self, jpeg_b64):
        try:
            from PIL import Image, ImageTk  # type: ignore
            import io
            img = Image.open(io.BytesIO(base64.b64decode(jpeg_b64)))
            self._imgref = ImageTk.PhotoImage(img)
            self._label.configure(image=self._imgref, text="")
        except Exception:
            # Pillow not present: show a placeholder text rather than crash.
            self._label.configure(text="[teacher screen]", image="")

    def kiosk(self, message="Focus"):
        # Strong FOCUS mode remains full-screen and blocking; ATTENTION is only
        # a non-blocking banner so teachers can choose the appropriate level.
        self.state = "focus"
        if self._ensure():
            try:
                self._root.attributes("-fullscreen", True)
                self._root.configure(bg="black")
                self._label.configure(text=message, image="", bg="black",
                                      fg="white", font=("Helvetica", 48, "bold"))
                self._root.deiconify()
                self._root.lift()
                self._root.update()
            except Exception:
                pass

    def hide(self):
        """Hard teardown, not just withdraw.  A classroom release must never
        leave a stale fullscreen/topmost Tk window behind."""
        self.state = "hidden"
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
            finally:
                self._root = None
                self._label = None


# ---------------------------------------------------------------------------
# Simulation hooks (non-macOS only) so tests can drive behaviour.
# ---------------------------------------------------------------------------
_sim_state = {"app": "TextEdit", "url": "https://khanacademy.org/x"}

def sim_set(app: Optional[str] = None, url: Optional[str] = None):
    if app is not None:
        _sim_state["app"] = app
    if url is not None:
        _sim_state["url"] = url


def get_idle_seconds() -> float:
    """Seconds since last user input. macOS via ioreg HIDIdleTime; else 0/sim."""
    if not IS_MAC:
        return float(_sim_state.get("idle", 0.0))
    try:
        out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], timeout=4,
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            if "HIDIdleTime" in line:
                ns = int(line.split("=")[-1].strip())
                return ns / 1_000_000_000.0
    except Exception:
        pass
    return 0.0
