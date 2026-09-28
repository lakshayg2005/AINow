"""
Manage admin accounts.

    python -m app.admin make-admin you@example.com
    python -m app.admin remove-admin you@example.com
    python -m app.admin set-password you@example.com
    python -m app.admin list
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.security import hash_password
from app.db.database import SessionLocal, engine
from app.db.models import User
from app.db.schema_patches import ensure_schema


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("make-admin", "remove-admin", "set-password"):
        sub.add_parser(command).add_argument("email")

    sub.add_parser("list")
    args = parser.parse_args()

    ensure_schema(engine)
    db = SessionLocal()

    try:
        if args.command == "list":
            admins = db.query(User).filter(User.is_admin.is_(True)).all()

            for user in admins:
                print(f"{user.id:>4}  {user.email}  ({user.name})")

            if not admins:
                print("No admins yet. Run: python -m app.admin make-admin <email>")

            return 0

        user = db.query(User).filter(User.email == args.email.strip().lower()).first()

        if user is None:
            # Emails are stored as registered; retry case-sensitively.
            user = db.query(User).filter(User.email == args.email.strip()).first()

        if user is None:
            print(f"No account with email {args.email}. Register on the site first.")
            return 1

        if args.command == "set-password":
            # Prompted, so the password stays out of shell history.
            password = getpass.getpass("New password: ")

            if not 8 <= len(password) <= 128:
                print("Password must be 8 to 128 characters.")
                return 1

            if password != getpass.getpass("Repeat password: "):
                print("Passwords do not match.")
                return 1

            user.password_hash = hash_password(password)
            db.commit()

            print(f"Password updated for {user.email}.")
            return 0

        user.is_admin = args.command == "make-admin"
        db.commit()

        print(f"{user.email} is {'now an admin' if user.is_admin else 'no longer an admin'}.")

        if user.is_admin and not user.is_email_verified:
            print("Note: this account's email is not verified yet, so it cannot log in.")

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
