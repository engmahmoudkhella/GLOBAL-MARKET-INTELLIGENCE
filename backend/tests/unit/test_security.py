import pytest

from app.core import security


def test_hash_and_verify_roundtrip():
    h = security.hash_password("a sufficiently long pw")
    assert h.startswith("$argon2id$")
    assert security.verify_password(h, "a sufficiently long pw")
    assert not security.verify_password(h, "wrong password!!")


def test_short_password_rejected():
    with pytest.raises(ValueError):
        security.hash_password("short")


def test_verify_with_garbage_hash_is_false():
    assert security.verify_password("not-a-hash", "whatever password") is False


def test_tokens_are_random_and_hash_is_stable():
    a, b = security.new_token(), security.new_token()
    assert a != b and len(a) >= 43
    assert security.hash_token(a) == security.hash_token(a)
    assert security.hash_token(a) != a
