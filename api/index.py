import sys
import os
from pathlib import Path

# Explicitly add the project root directory (/var/task) to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

cravin_dir = root_dir / "Cravin"
if cravin_dir.is_dir() and str(cravin_dir) not in sys.path:
    sys.path.insert(0, str(cravin_dir))

# Add current directory as fallback
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from app.main import app
