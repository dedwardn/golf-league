import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta


def test_utc_now_is_naive_utc() -> None:
    # A process of its own: the Python uv installs has no time.tzset, so TZ only counts at start.
    # Nine hours from UTC, so a read of the local clock fails on any machine.
    code = "from league.services.clock import utc_now; print(utc_now().isoformat())"
    env = {**os.environ, "TZ": "Asia/Tokyo"}
    run = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    now = datetime.fromisoformat(run.stdout.strip())
    assert now.tzinfo is None
    assert abs(datetime.now(UTC).replace(tzinfo=None) - now) < timedelta(minutes=1)
