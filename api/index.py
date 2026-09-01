import sys
import os

# Add root folder to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)
cravin_dir = os.path.join(root_dir, "Cravin")
if os.path.isdir(cravin_dir) and cravin_dir not in sys.path:
    sys.path.append(cravin_dir)

from app.main import app
