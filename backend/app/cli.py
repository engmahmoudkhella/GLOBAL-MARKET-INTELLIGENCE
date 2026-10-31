"""Operator CLI. There is no public signup (decision D2); accounts are created here.

Usage:
  uv run python -m app.cli create-user --email you@example.com --name "Owner" --role admin
  uv run python -m app.cli set-password --email you@example.com
"""

from __future__ import annotations

import getpass
import sys

import typer
from sqlalchemy import select

from app.auth import service
from app.core.db import get_sessionmaker
from app.models import User

cli = typer.Typer(no_args_is_help=True, add_completion=False)


def _read_password(stdin: bool) -> str:
    if stdin:
        return sys.stdin.readline().rstrip("\n")
    pw = getpass.getpass("Password: ")
    if pw != getpass.getpass("Repeat password: "):
        typer.echo("Passwords do not match", err=True)
        raise typer.Exit(1)
    return pw


@cli.command("create-user")
def create_user(
    email: str = typer.Option(...),
    name: str = typer.Option(...),
    role: str = typer.Option("viewer", help="admin | analyst | viewer"),
    language: str = typer.Option("ar", help="ar | en"),
    timezone: str = typer.Option(None, help="IANA timezone; default GMI_DEFAULT_TIMEZONE"),
    password_stdin: bool = typer.Option(False, help="Read password from stdin"),
) -> None:
    password = _read_password(password_stdin)
    with get_sessionmaker()() as session:
        try:
            user = service.create_user(
                session,
                email=email,
                name=name,
                password=password,
                role=role,
                preferred_language=language,
                timezone=timezone,
            )
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from None
        session.commit()
        typer.echo(f"Created user id={user.id} email={user.email} role={user.role}")


@cli.command("set-password")
def set_password(
    email: str = typer.Option(...),
    password_stdin: bool = typer.Option(False),
) -> None:
    password = _read_password(password_stdin)
    with get_sessionmaker()() as session:
        user = session.scalar(select(User).where(User.email == service.normalize_email(email)))
        if user is None:
            typer.echo("No such user", err=True)
            raise typer.Exit(1)
        try:
            service.set_password(session, user, password)
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from None
        session.commit()
        typer.echo("Password updated; existing sessions revoked.")


if __name__ == "__main__":
    cli()
