"""Production server entry point using waitress."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from waitress import serve
from app.main import app

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting Finance Tracker on {host}:{port}")
    serve(app, host=host, port=port, threads=4)
