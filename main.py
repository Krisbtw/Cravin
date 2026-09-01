import sys
import os

# Ensure current directory and Cravin directory are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

cravin_dir = os.path.join(current_dir, "Cravin")
if os.path.isdir(cravin_dir) and cravin_dir not in sys.path:
    sys.path.insert(0, cravin_dir)

from app.main import app

# Explicitly expose application and handler aliases for Vercel Python runtime
application = app
handler = app

__all__ = ["app", "application", "handler"]
