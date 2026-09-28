"""PyInstaller entry point for the Teacher Console (TeacherConsole.app).

Starts the console server and opens the local UI in the default browser so the
teacher just double-clicks the app and sees the console.
"""
import os, sys, threading, time, webbrowser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _open_when_up(port):
    time.sleep(1.5)
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.environ.get("ACOS_PORT", "8770"))
    threading.Thread(target=_open_when_up, args=(port,), daemon=True).start()
    # Reuse the server's main(); pass through default args.
    from teacher.server import main
    sys.argv = [sys.argv[0], "--port", str(port)]
    main()
