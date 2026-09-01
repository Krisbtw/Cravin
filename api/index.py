import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
cravin_dir = ROOT_DIR / "Cravin"
if cravin_dir.is_dir() and str(cravin_dir) not in sys.path:
    sys.path.insert(0, str(cravin_dir))

from app.main import app
