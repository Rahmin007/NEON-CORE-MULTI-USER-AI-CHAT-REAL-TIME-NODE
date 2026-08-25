from pathlib import Path
import sys

# Make the project root importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.security import get_password_hash
from app.db.session import SessionLocal, init_db
from app.models.user import User, UserRole


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip()
        password = input("Admin password: ").strip()
        if not username or not email or not password:
            raise SystemExit("Username, email, and password are required.")
        if db.query(User).filter((User.username == username) | (User.email == email)).first():
            raise SystemExit("A user with that username or email already exists.")
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin created successfully: {username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
