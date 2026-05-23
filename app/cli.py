"""CLI entry point: python -m app.cli <command> [options]"""
import argparse
import getpass
import os
import shutil
import sys
from datetime import datetime, timezone

# Ensure project root is on path when run as module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _get_db():
    from app.db import SessionLocal
    return SessionLocal()


def cmd_create_admin(args):
    from app.db import engine
    from app.models import Base, User
    from app.auth import hash_pin

    # Ensure data dir and tables exist
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(engine)

    pin = getpass.getpass(f"PIN for '{args.name}' (4-8 digits): ")
    if not pin.isdigit() or not (4 <= len(pin) <= 8):
        print("Error: PIN must be 4-8 digits.", file=sys.stderr)
        sys.exit(1)

    db = _get_db()
    try:
        existing = db.query(User).filter_by(name=args.name).first()
        if existing:
            print(f"Error: user '{args.name}' already exists.", file=sys.stderr)
            sys.exit(1)
        user = User(
            name=args.name,
            pin_hash=hash_pin(pin),
            created_at=datetime.now(timezone.utc),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin user '{args.name}' created (id={user.id}).")
    finally:
        db.close()


def cmd_seed_categories(args):
    from app.db import engine
    from app.models import Base, Category

    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(engine)

    SEED = [
        ("Food", None, "#f59e0b"),
        ("Essentials", None, "#3b82f6"),
        ("Subscriptions", None, "#8b5cf6"),
        ("Transport", None, "#10b981"),
        ("Healthcare", None, "#ef4444"),
        ("Leisure", None, "#ec4899"),
        ("Loans", None, "#f97316"),
        ("Insurance", None, "#6366f1"),
        ("Other", None, "#6b7280"),
    ]
    ESSENTIALS_CHILDREN = [
        ("Electricity", "#fbbf24"),
        ("Water", "#60a5fa"),
        ("Gas / Heating", "#fb923c"),
        ("Internet", "#a78bfa"),
        ("Phone", "#34d399"),
    ]

    db = _get_db()
    try:
        if db.query(Category).count() > 0:
            print("Categories already seeded — skipping.")
            return

        created = {}
        for name, parent_name, color in SEED:
            cat = Category(name=name, color=color)
            db.add(cat)
            db.flush()
            created[name] = cat.id

        essentials_id = created["Essentials"]
        for name, color in ESSENTIALS_CHILDREN:
            db.add(Category(name=name, parent_id=essentials_id, color=color))

        db.commit()
        print(f"Seeded {len(SEED) + len(ESSENTIALS_CHILDREN)} categories.")
    finally:
        db.close()


def cmd_backup(args):
    import glob
    src = "data/finance.db"
    if not os.path.exists(src):
        print("Error: data/finance.db not found.", file=sys.stderr)
        sys.exit(1)
    os.makedirs("data/backups", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"data/backups/finance-{ts}.db"
    shutil.copy2(src, dst)
    print(f"Backup written to {dst}")


def main():
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command")

    p_admin = sub.add_parser("create-admin", help="Create an admin user")
    p_admin.add_argument("--name", required=True, help="Username")

    sub.add_parser("seed-categories", help="Seed default categories")
    sub.add_parser("backup", help="Backup the database")

    args = parser.parse_args()
    if args.command == "create-admin":
        cmd_create_admin(args)
    elif args.command == "seed-categories":
        cmd_seed_categories(args)
    elif args.command == "backup":
        cmd_backup(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
