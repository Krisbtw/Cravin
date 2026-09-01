import sys
import os

# Ensure Cravin project root is in sys.path
cravin_dir = os.path.join(os.path.dirname(__file__), "Cravin")
if os.path.isdir(cravin_dir) and cravin_dir not in sys.path:
    sys.path.insert(0, cravin_dir)

try:
    from app.main import app
except ImportError:
    from Cravin.app.main import app
