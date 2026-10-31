from app.core.rate_limit import MemoryBackend


def test_fixed_window_blocks_after_limit_and_resets():
    now = [1_000_020.0]
    b = MemoryBackend(clock=lambda: now[0])
    assert all(b.hit("k", 3, 60).allowed for _ in range(3))
    d = b.hit("k", 3, 60)
    assert not d.allowed and 0 < d.retry_after <= 60
    assert b.hit("other", 3, 60).allowed  # keys are independent
    now[0] += 60
    assert b.hit("k", 3, 60).allowed
