import sys
from pathlib import Path

# Add project root directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))
cravin_path = Path(__file__).resolve().parent / "Cravin"
if cravin_path.is_dir():
    sys.path.insert(0, str(cravin_path))

from app.main import app
