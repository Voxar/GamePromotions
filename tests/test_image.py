"""Builds the real image and runs it.

The old Dockerfile copied a file that no longer exists and omitted every
application package -- the kind of breakage only an actual build catches.
"""
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
COMPOSE = REPO / "docker-compose.yml"
IMAGE_TAG = "gamepromotions:pytest"


def docker_available():
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


requires_docker = pytest.mark.skipif(not docker_available(), reason="docker unavailable")


@pytest.fixture(scope="module")
def image():
    build = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, str(REPO)],
        capture_output=True, text=True, timeout=900,
    )
    assert build.returncode == 0, build.stderr[-4000:]
    yield IMAGE_TAG
    subprocess.run(["docker", "rmi", "-f", IMAGE_TAG], capture_output=True)


def run_in_image(image, *args, env=None, timeout=120):
    cmd = ["docker", "run", "--rm", "--network", "none"]
    for key, value in (env or {}).items():
        cmd += ["-e", f"{key}={value}"]
    return subprocess.run([*cmd, image, *args], capture_output=True, text=True, timeout=timeout)


@requires_docker
class TestImage:
    def test_main_and_every_source_are_importable(self, image):
        """Proves the image ships all packages main.py reaches for at runtime."""
        modules = "import main, models.games, models.game, sources.epic_games, " \
                  "sources.steam, sources.gog, destinations.discord, databases.mongodb"
        result = run_in_image(image, "python", "-c", modules)
        assert result.returncode == 0, result.stderr[-4000:]

    def test_ships_the_scheduler(self, image):
        result = run_in_image(image, "supercronic", "-version")
        assert result.returncode == 0, result.stderr[-2000:]

    def test_scheduler_accepts_our_crontab(self, image):
        """supercronic -test validates the schedule without running anything."""
        result = run_in_image(image, "supercronic", "-test", "/app/crontab")
        assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]

    def test_does_not_run_as_root(self, image):
        result = run_in_image(image, "id", "-u")
        assert result.stdout.strip() != "0", "container must not run as root"


class TestCompose:
    def test_passes_every_secret_the_job_needs(self):
        compose = yaml.safe_load(COMPOSE.read_text())
        services = compose["services"]
        assert len(services) == 1, f"expected a single service, got {list(services)}"
        env = next(iter(services.values()))["environment"]
        keys = set(env) if isinstance(env, dict) else {e.split("=", 1)[0] for e in env}
        assert {
            "DISCORD_WEBHOOK_URL", "MONGODB_URI", "SENTRY_DSN",
            "EPIC_GAMES_PROMOTIONS", "STEAM_PROMOTIONS", "GOG_PROMOTIONS",
        } <= keys

    def test_service_is_single_homed(self):
        """A second network makes Coolify's Traefik route to an unreachable IP."""
        compose = yaml.safe_load(COMPOSE.read_text())
        service = next(iter(compose["services"].values()))
        assert "networks" not in service

    def test_caps_memory(self):
        """Etiquette on the shared box: nothing unbounded."""
        compose = yaml.safe_load(COMPOSE.read_text())
        service = next(iter(compose["services"].values()))
        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        assert limits.get("memory"), "set a memory limit"
