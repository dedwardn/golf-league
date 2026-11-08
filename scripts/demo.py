"""The demo: the golden seasons served on the local network, and phone-width shots of its pages.

    uv run --with playwright python scripts/demo.py serve
    uv run --with playwright python scripts/demo.py shots <player> <path>... --out <dir>

`shots admin` signs in through the demo admin link in place of a player's.

Install Chromium once with `uv run --with playwright playwright install chromium`.
"""

import argparse
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import ViewportSize, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from fixtures.database import WINDOW_OPENS, a_template
from fixtures.team_season import t3_open
from league.services.runtime import open_database
from league.store.save import save_window

# Outside the repo, and the same place every run, so a later serve finds the demo to stop.
FOLDER = Path(tempfile.gettempdir()) / "league-demo"
DATABASE = FOLDER / "league.db"
PID_FILE = FOLDER / "demo.pid"
LOG = FOLDER / "uvicorn.log"
SEASON_ID = "t3-open"
# The demo's own admin secret (D19), so the owner can open the admin screens on the laptop.
ADMIN_TOKEN = "demo-admin"
OPEN_ROUNDS = (1, 3)
PORT = 8016
LOCAL = f"http://127.0.0.1:{PORT}"
ZONE = ZoneInfo("Europe/Oslo")
PHONE: ViewportSize = {"width": 390, "height": 844}


def coming_sunday_close(now: datetime) -> datetime:
    """22:00 Oslo time on the next Sunday not yet past, in naive UTC as the store holds time."""
    local = now.astimezone(ZONE)
    days = (6 - local.weekday()) % 7
    sunday = (local + timedelta(days=days)).replace(hour=22, minute=0, second=0, microsecond=0)
    if sunday <= local:
        sunday += timedelta(days=7)
    return sunday.astimezone(UTC).replace(tzinfo=None)


def _is_demo(pid: int) -> bool:
    """Whether the pid is still the demo server, since a stale pid may name another process."""
    ps = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, check=False)
    return b"league.web.app:create_app" in ps.stdout


def stop_earlier_demo() -> None:
    if not PID_FILE.exists():
        return
    pid = int(PID_FILE.read_text())
    PID_FILE.unlink()
    if not _is_demo(pid):
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not _is_demo(pid):
            return
        time.sleep(0.1)
    sys.exit(f"The earlier demo, process {pid}, did not stop.")


def _listening() -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", PORT)) == 0


def port_taken() -> bool:
    """Whether anything holds the port, including a server bound to one address only."""
    if _listening():
        return True
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("0.0.0.0", PORT))
        except OSError:
            return True
    return False


def build_database() -> None:
    a_template(FOLDER, {SEASON_ID: t3_open()})
    closes_at = coming_sunday_close(datetime.now(UTC))
    engine = open_database(DATABASE)
    with engine.begin() as connection:
        for number in OPEN_ROUNDS:
            save_window(connection, SEASON_ID, number, WINDOW_OPENS, closes_at)
    engine.dispose()


def start_server() -> None:
    """Uvicorn in its own session, so it outlives this script, and back once it answers."""
    env = {
        **os.environ,
        "LEAGUE_DATABASE": str(DATABASE),
        "LEAGUE_SEASON": SEASON_ID,
        "LEAGUE_ADMIN_TOKEN": ADMIN_TOKEN,
    }
    app = ["uvicorn", "--factory", "league.web.app:create_app"]
    command = [sys.executable, "-m", *app, "--host", "0.0.0.0", "--port", str(PORT)]
    with LOG.open("w") as log:
        server = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
    PID_FILE.write_text(str(server.pid))
    for _ in range(100):
        if server.poll() is not None:
            sys.exit(f"The server stopped. See {LOG}.")
        if _listening():
            return
        time.sleep(0.1)
    sys.exit(f"The server did not answer on port {PORT}. See {LOG}.")


def lan_address() -> str:
    """The address the Mac's default route leaves from. Connecting a UDP socket sends nothing."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]


def serve() -> None:
    stop_earlier_demo()
    if port_taken():
        sys.exit(
            f"Port {PORT} is held by a process this script did not start. "
            f"Find it with `lsof -nP -iTCP:{PORT}`, stop it, and run serve again."
        )
    shutil.rmtree(FOLDER, ignore_errors=True)
    FOLDER.mkdir()
    build_database()
    start_server()
    address = lan_address()
    sys.stdout.write(f"Serving {SEASON_ID} from {DATABASE}\n")
    for player in sorted(t3_open().seed_index_tenths):
        sys.stdout.write(f"{player}: http://{address}:{PORT}/k/{player}-link\n")
    sys.stdout.write(f"admin: http://{address}:{PORT}/admin/k/{ADMIN_TOKEN}\n")


def shots(player: str, paths: list[str], out: Path) -> None:
    """One full-page PNG per path at 390 px wide, in a browser that opened the player's link, or
    the admin's for `admin`."""
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=PHONE, device_scale_factor=2)
        link = f"/admin/k/{ADMIN_TOKEN}" if player == "admin" else f"/k/{player}-link"
        signed_in = page.goto(LOCAL + link)
        if signed_in is None or not signed_in.ok:
            sys.exit(f"{link} did not sign in. Is the demo served?")
        for path in paths:
            page.set_viewport_size(PHONE)
            response = page.goto(LOCAL + path)
            status = "no response" if response is None else response.status
            # A full-page shot draws the fixed nav where the viewport ends, over the content, so
            # the viewport grows to the page and the nav sits at the bottom as on a scrolled phone.
            height = page.evaluate("document.documentElement.scrollHeight")
            page.set_viewport_size({"width": PHONE["width"], "height": height})
            target = out / f"{player}_{re.sub(r'\W+', '_', path).strip('_') or 'home'}.png"
            page.screenshot(path=target, full_page=True)
            sys.stdout.write(f"{status} {path} -> {target}\n")
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    shot = commands.add_parser("shots")
    shot.add_argument("player")
    shot.add_argument("paths", nargs="+")
    shot.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        serve()
    else:
        shots(args.player, args.paths, args.out)


if __name__ == "__main__":
    main()
