"""CLI tool for managing Yak Shears users.

Run with:

```sh
uv run yak-shears-users list
```

"""

import argparse
import getpass
import sys
from datetime import datetime

from yak_shears._auth.models import Password
from yak_shears._auth.storage import create_user, delete_user, get_user_by_email, list_all_users
from yak_shears._log_utils import log


def _create_user_command(args: argparse.Namespace) -> None:
    """Create a new user.

    Args:
        args: Parsed command line arguments
    """
    email = args.email
    display_name = args.display_name or email

    if get_user_by_email(email):
        log(f"Error: User with email '{email}' already exists", file=sys.stderr)
        sys.exit(1)

    if not (password := Password(getpass.getpass("Enter password: "))):
        log("Error: Password cannot be empty", file=sys.stderr)
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm password: ")
    if password != password_confirm:
        log("Error: Passwords do not match", file=sys.stderr)
        sys.exit(1)

    try:
        user = create_user(email, display_name, password)
        log(f"Successfully created user: {user['email']} ({user['display_name']})")
        log(f"User ID: {user['id']}")
    except ValueError as e:
        log(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _list_users_command(_args: argparse.Namespace) -> None:
    """List all users.

    Args:
        _args: Parsed command line arguments (unused)
    """
    users = list_all_users()

    if not users:
        log("No users found.")
        return

    log(f"Found {len(users)} users")
    fmt = "%Y-%m-%d %H:%M:%S"
    for user in users:
        last_login = datetime.fromisoformat(user["last_login"]).strftime(fmt) if user["last_login"] else "Never"
        created_at = datetime.fromisoformat(user["created_at"]).strftime(fmt)

        summary = f"""
       Email: {user["email"]}
Display Name: {user["display_name"]}
     Created: {created_at}
  Last Login: {last_login}
     User ID: {user["id"]}
"""
        log(f"{'-' * 40}\n{summary.strip()}")


def _delete_user_command(args: argparse.Namespace) -> None:
    """Delete a user.

    Args:
        args: Parsed command line arguments
    """
    email = args.email

    if not (user := get_user_by_email(email)):
        log(f"Error: User with email '{email}' not found", file=sys.stderr)
        sys.exit(1)

    log(f"About to delete user: {user['email']} ({user['display_name']})")
    confirm = input("Are you sure? Type 'yes' to confirm: ")

    if confirm.lower() != "yes":
        log("Deletion cancelled.")
        return

    if delete_user(email):
        log(f"Successfully deleted user: {email}")
    else:
        log(f"Error: Failed to delete user: {email}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Manage Yak Shears users", prog="yak-shears-users")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    create_parser = subparsers.add_parser("create", help="Create a new user")
    create_parser.add_argument("email", help="User email address")
    create_parser.add_argument("--display-name", help="User display name (defaults to email)")
    create_parser.set_defaults(func=_create_user_command)

    list_parser = subparsers.add_parser("list", help="List all users")
    list_parser.set_defaults(func=_list_users_command)

    delete_parser = subparsers.add_parser("delete", help="Delete a user")
    delete_parser.add_argument("email", help="Email of user to delete")
    delete_parser.set_defaults(func=_delete_user_command)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
