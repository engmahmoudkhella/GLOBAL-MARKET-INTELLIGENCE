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


@cli.command("backfill-candles")
def backfill_candles(
    symbol: str = typer.Option("BTCUSD"),
    provider: str = typer.Option("coinbase"),
    timeframe: str = typer.Option("1h", help="1m | 5m | 15m | 1h | 1d"),
    days: int = typer.Option(30, min=1, max=3650),
) -> None:
    """Import historical candles (validated; nothing is filled). Safe to re-run."""
    from datetime import timedelta

    from app.core.clock import utcnow
    from app.ingestion import service
    from app.providers import registry

    adapter = registry.create(provider)
    end = utcnow()
    start = end - timedelta(days=days)
    with get_sessionmaker()() as session:
        try:
            r = service.ingest_candles(
                session,
                symbol,
                adapter,
                timeframe,  # type: ignore[arg-type]
                start,
                end,
            )
        finally:
            adapter.close()
        session.commit()
    typer.echo(
        f"ok={r.ok} stored={r.stored} skipped={r.skipped} statuses={r.statuses} "
        f"issues={r.issues} error={r.error}"
    )
    if not r.ok:
        raise typer.Exit(1)


@cli.command("backfill-reference")
def backfill_reference(
    symbol: str = typer.Option("USDILS"),
    days: int = typer.Option(365, min=1, max=3650),
) -> None:
    """Import Bank of Israel representative rates (reference only, never quotes)."""
    from datetime import timedelta

    from app.core.clock import utcnow
    from app.ingestion import service
    from app.providers import registry

    adapter = registry.create("boi")
    today = utcnow().date()
    with get_sessionmaker()() as session:
        try:
            r = service.ingest_reference_rates(
                session, symbol, adapter, today - timedelta(days=days), today
            )
        finally:
            adapter.close()
        session.commit()
    typer.echo(f"ok={r.ok} stored={r.stored} skipped={r.skipped} issues={r.issues} error={r.error}")
    if not r.ok:
        raise typer.Exit(1)


@cli.command("boi-publication-stats")
def boi_publication_stats() -> None:
    """Median and range of observed BoI publication times (Israel local). Report only."""
    from app.ingestion.boi_stats import publication_stats

    with get_sessionmaker()() as session:
        st = publication_stats(session)
    verdict = "sufficient" if st.sufficient else "INSUFFICIENT - do not decide yet"
    typer.echo(f"business days observed: {st.business_days}/{st.required} ({verdict})")
    typer.echo(f"period: {st.first_date} .. {st.last_date}")
    typer.echo(
        f"median {st.median_local}, range {st.earliest_local} - {st.latest_local} "
        f"(Asia/Jerusalem); configured fallback {st.configured_fallback} (unchanged)"
    )


@cli.command("verify-holiday")
def verify_holiday(
    symbol: str = typer.Option("XAUUSD"),
    provider: str = typer.Option("twelvedata"),
    day: str = typer.Option(..., help="Session day (YYYY-MM-DD), e.g. 2027-03-26"),
) -> None:
    """Report what data actually exists for a session day ending 17:00 New York on `day`
    (used to confirm or reject holiday assumptions such as Good Friday for XAUUSD)."""
    from datetime import date

    from sqlalchemy import func, select

    from app.ingestion import service
    from app.markets.calendars import special_closure_window
    from app.models import MarketCandle, MarketQuote

    start, end = special_closure_window("xau", date.fromisoformat(day))
    with get_sessionmaker()() as session:
        t = service.resolve(session, symbol, provider)
        for label, model, col in (
            ("1h candles", MarketCandle, MarketCandle.open_time),
            ("quotes", MarketQuote, MarketQuote.observed_at),
        ):
            stmt = select(model.data_quality_status, func.count()).where(
                model.instrument_id == t.instrument.id,
                model.provider_id == t.provider.id,
                col >= start,
                col < end,
            )
            if model is MarketCandle:
                stmt = stmt.where(MarketCandle.timeframe == "1h")
            counts = dict(session.execute(stmt.group_by(model.data_quality_status)).all())
            typer.echo(f"{symbol} {label} {start.isoformat()} .. {end.isoformat()}: {counts}")
        flagged = [w.name for w in t.reduced_liquidity if w.start < end and start < w.end]
        typer.echo(f"calendar marks this day as: {flagged or 'normal session'}")


if __name__ == "__main__":
    cli()
