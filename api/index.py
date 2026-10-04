import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from Backend.app import app

# Vercel looks for a callable named app in the serverless function.
# The imported Flask app from Backend/app.py already satisfies that contract.
