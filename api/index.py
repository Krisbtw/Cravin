import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
cravin_dir = os.path.join(project_root, "Cravin")
if os.path.isdir(cravin_dir) and cravin_dir not in sys.path:
    sys.path.insert(0, cravin_dir)

from app.main import app
