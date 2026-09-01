import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Also add Cravin subdirectory if present
cravin_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "Cravin")
if os.path.isdir(cravin_dir):
    sys.path.insert(0, cravin_dir)

from app.main import app

application = app
handler = app
