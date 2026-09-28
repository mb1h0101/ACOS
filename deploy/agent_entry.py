"""PyInstaller entry point for the Student Agent binary (acos-agent)."""
import os, sys
# When frozen, the package modules are bundled; ensure repo root style imports work.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent.main import main
if __name__ == "__main__":
    main()
