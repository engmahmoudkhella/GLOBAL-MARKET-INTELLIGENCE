import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.audit import service as audit
from app.jobs.runner import run_idempotent
from tests.integration.conftest import make_user

pytestmark = pytest.mark.integration


def test_audit_log_is_append_only(db):
    audit.record(db, "test.event", details={"a": 1})
    db.commit()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE system_audit_logs SET action='tampered'"))
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM system_audit_logs"))
    db.rollback()
    assert db.execute(text("SELECT action FROM system_audit_logs")).scalar() == "test.event"


def test_deleting_user_keeps_audit_rows(db):
    uid = make_user(db)
    db.execute(text("DELETE FROM users WHERE id=:id"), {"id": uid})
    db.commit()
    rows = db.execute(text("SELECT user_id, action FROM system_audit_logs")).all()
    assert rows and all(r.user_id is None for r in rows)


def test_job_runner_is_idempotent(db):
    calls = []
    assert run_idempotent(db, "t", "t:1", lambda: calls.append(1) or {"n": 1}) == "succeeded"
    assert run_idempotent(db, "t", "t:1", lambda: calls.append(1)) == "skipped"
    assert calls == [1]


def test_failed_job_can_be_retried(db):
    def boom():
        raise RuntimeError("provider timeout")

    with pytest.raises(RuntimeError):
        run_idempotent(db, "t", "t:2", boom)
    row = db.execute(text("SELECT status, error FROM job_runs WHERE idempotency_key='t:2'")).one()
    assert row.status == "failed" and "provider timeout" in row.error
    assert run_idempotent(db, "t", "t:2", lambda: None) == "succeeded"


def test_heartbeat_task_records_job_run(db, monkeypatch):
    from app.tasks import system

    assert system.heartbeat.run() == "succeeded"
    assert system.heartbeat.run() == "skipped"  # same minute
    assert db.execute(text("SELECT count(*) FROM job_runs")).scalar() == 1
