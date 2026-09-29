"""PyInstaller entry point for the Teacher Console (TeacherConsole.app).

Starts the console server and opens the local UI in the default browser so the
teacher just double-clicks the app and sees the console.
"""
import os, sys, threading, time, webbrowser, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _open_when_up(port):
    time.sleep(1.0)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass

def _port_has_listener(port):
    """Return True only when something is already accepting TCP on the console port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False

if __name__ == "__main__":
    port = int(os.environ.get("ACOS_PORT", "8770"))

    # Single-instance behaviour: if Teacher Console is already running, do not
    # crash with EADDRINUSE. Just bring the existing web console to the teacher.
    if _port_has_listener(port):
        webbrowser.open(f"http://127.0.0.1:{port}")
        sys.exit(0)

    threading.Thread(target=_open_when_up, args=(port,), daemon=True).start()
    from teacher.server import main
    sys.argv = [sys.argv[0], "--port", str(port)]
    main()
