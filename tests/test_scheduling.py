"""The container schedules itself; nothing is installed on the host.

These tests pin the contract between the crontab, the entrypoint and supercronic,
since a broken schedule fails silently in production -- the container stays up and
healthy while simply never running the job.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CRONTAB = REPO / "crontab"
ENTRYPOINT = REPO / "docker-entrypoint.sh"


def crontab_jobs():
    """Non-comment crontab entries as (schedule, command) pairs."""
    jobs = []
    for line in CRONTAB.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(maxsplit=5)
        assert len(fields) == 6, f"not a 5-field cron entry: {line!r}"
        jobs.append((" ".join(fields[:5]), fields[5]))
    return jobs


class TestCrontab:
    def test_runs_the_job_every_four_hours(self):
        jobs = crontab_jobs()
        assert len(jobs) == 1, f"expected exactly one job, got {jobs}"
        schedule, command = jobs[0]
        assert schedule == "0 */4 * * *"
        assert "main.py" in command

    def test_job_is_invoked_from_the_app_directory(self):
        """main.py resolves sibling packages by cwd, so cron must not run it from /."""
        _, command = crontab_jobs()[0]
        assert "/app" in command


def write_stub(directory: Path, name: str, body: str):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def sandbox(tmp_path):
    """Run the entrypoint against stub `python`/`supercronic` that record their calls."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls.log"

    def run(env=None, python_exit=0):
        write_stub(bindir, "python", f'echo "python $*" >> {log}\nexit {python_exit}\n')
        write_stub(bindir, "supercronic", f'echo "supercronic $*" >> {log}\nexit 0\n')
        result = subprocess.run(
            ["sh", str(ENTRYPOINT)],
            env={"PATH": f"{bindir}:/usr/bin:/bin", **(env or {})},
            capture_output=True,
            text=True,
            timeout=30,
        )
        calls = log.read_text().splitlines() if log.exists() else []
        return result, calls

    return run


class TestEntrypoint:
    def test_starts_the_scheduler(self, sandbox):
        result, calls = sandbox()
        assert result.returncode == 0, result.stderr
        assert any(c.startswith("supercronic") for c in calls), calls

    def test_passes_the_crontab_to_the_scheduler(self, sandbox):
        _, calls = sandbox()
        supercronic = next(c for c in calls if c.startswith("supercronic"))
        assert "crontab" in supercronic

    def test_skips_the_immediate_run_by_default(self, sandbox):
        """A redeploy must not fire an unscheduled post run unless asked to."""
        _, calls = sandbox()
        assert not any(c.startswith("python") for c in calls), calls

    def test_runs_the_job_immediately_when_asked(self, sandbox):
        _, calls = sandbox(env={"RUN_ON_START": "true"})
        assert calls[0].startswith("python"), calls
        assert "main.py" in calls[0]
        assert any(c.startswith("supercronic") for c in calls), calls

    def test_starts_the_scheduler_even_if_the_immediate_run_fails(self, sandbox):
        """A transient API failure at boot must not cost us the whole schedule."""
        result, calls = sandbox(env={"RUN_ON_START": "true"}, python_exit=1)
        assert result.returncode == 0, result.stderr
        assert any(c.startswith("supercronic") for c in calls), calls
