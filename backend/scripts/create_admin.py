"""Create an admin account interactively:  python -m scripts.create_admin"""
import asyncio
import getpass

from app.db import mongo
from app.schemas.models import Role
from app.services import store


async def main() -> None:
    mongo.connect()
    await mongo.init_indexes()
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin password (min 8 characters): ")
    if not username or not email or len(password) < 8:
        raise SystemExit("Username, email and a password of at least 8 characters are required.")
    try:
        await store.create_user(username, email, password, Role.ADMIN.value)
    except store.AlreadyExists:
        raise SystemExit("A user with that username or email already exists.") from None
    print(f"Admin '{username}' created.")
    await mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
