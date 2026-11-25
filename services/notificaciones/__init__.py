"""Notificaciones microservice (Sprint 5)."""

import logging
import sys
from pathlib import Path

# Allow this service to run from its own folder while reusing the
# repository's shared/ package (works locally and inside the containers).
REPO_ROOT = None
for _parent in Path(__file__).resolve().parents:
    if (_parent / "shared" / "database.py").exists():
        REPO_ROOT = _parent
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
if REPO_ROOT is None:
    REPO_ROOT = Path(__file__).resolve().parents[3]
