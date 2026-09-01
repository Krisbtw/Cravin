import sys
import os

# Add project root directory to sys.path before any internal imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
cravin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Cravin")
if os.path.isdir(cravin_dir) and cravin_dir not in sys.path:
    sys.path.insert(0, cravin_dir)

from app.main import app
