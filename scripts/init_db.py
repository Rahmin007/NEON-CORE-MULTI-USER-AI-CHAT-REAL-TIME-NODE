from pathlib import Path
import sys

# Make the project root importable when this file is run directly:
#   python scripts\init_db.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import init_db, engine


if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully: {engine.url}")
