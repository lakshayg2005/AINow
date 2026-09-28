"""
Manage admin accounts and stuck pipeline jobs.

    python -m app.admin make-admin you@example.com
    python -m app.admin remove-admin you@example.com
    python -m app.admin set-password you@example.com
    python -m app.admin verify-email you@example.com
    python -m app.admin create-token you@example.com [--days 400]
    python -m app.admin list
    python -m app.admin cancel-job <id>
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.security import create_service_token, hash_password
from app.db.database import SessionLocal, engine
from app.db.models import PipelineJob, User
from app.db.schema_patches import ensure_schema
from app.ingest.utils import utcnow


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("make-admin", "remove-admin", "set-password", "verify-email"):
        sub.add_parser(command).add_argument("email")

    token_parser = sub.add_parser("create-token")
    token_parser.add_argument("email")
    token_parser.add_argument(
        "--days",
        type=int,
        default=400,
        help="Validity in days (default 400).",
    )

    sub.add_parser("list")

    cancel_parser = sub.add_parser("cancel-job")
    cancel_parser.add_argument("job_id", type=int)

    args = parser.parse_args()

    ensure_schema(engine)
    db = SessionLocal()

    try:
        if args.command == "cancel-job":
            job = db.get(PipelineJob, args.job_id)

            if job is None:
                print(f"No job #{args.job_id}.")
                return 1

            if job.status not in ("queued", "running"):
                print(f"Job #{job.id} is already {job.status}; nothing to cancel.")
                return 0

            # This only updates the database row — it can't stop
            # a thread that's actually still hung inside the live
            # process. Restart the backend too (a redeploy is the
            # simplest way) so the stuck work is actually gone.
            job.status = "failed"
            job.error = "Cancelled manually (was stuck)."
            job.finished_at = utcnow()
            db.commit()

            print(f"Job #{job.id} marked failed. Restart the backend so the stuck work actually stops.")
            return 0

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

        if args.command == "create-token":
            if not user.is_admin:
                print(f"{user.email} is not an admin; /admin/jobs/* would reject this token.")
                return 1

            token = create_service_token(user.id, days=args.days)

            print(
                f"Bearer token for {user.email}, valid {args.days} days.\n"
                "Store it as a secret (e.g. a GitHub Actions repo secret named "
                "ADMIN_TOKEN) — it will not be shown again:\n"
            )
            print(token)
            return 0

        if args.command == "verify-email":
            if user.is_email_verified:
                print(f"{user.email} is already verified.")
                return 0

            user.is_email_verified = True
            db.commit()

            print(f"{user.email} is now verified and can log in.")
            return 0

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
