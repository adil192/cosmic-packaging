"""Full automated pipeline for the Fedora COSMIC packaging workflow.

Handles the complete lifecycle:
  1. SSH agent setup & Kerberos authentication
  2. Side tag creation in Koji
  3. Looping until all builds finish: check Koji status, queue builds for
     packages that are not already BUILDING or COMPLETE at the target
     version, then wait between checks
  4. Optionally creating Bodhi updates for each Fedora release
"""

import argparse
import contextlib
import datetime
import functools
import glob
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.request import urlopen, urlretrieve

# Koji build info is returned as a plain dict with mixed value types
KojiBuild = dict[str, Any]

import koji
import requests
import rpm
from cosmic_common import (
    FEDORA_BRANCHES,
    PACKAGES,
    RAWHIDE_BRANCH,
    RAWHIDE_NUMBER,
    SIDE_TAG_BRANCHES,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(
    handlers=[
        logging.FileHandler("cosmic-packaging-automation.log"),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KOJI_HUB = "https://koji.fedoraproject.org/kojihub"

FEDORA_TAGS: dict[str, str] = {
    "Rawhide": "fc46",
    "F45": "fc45",
    "F44": "fc44",
    "F43": "fc43",
}

FEDORA_RELEASES: dict[str, str] = {
    "fc46": "Rawhide",
    "fc45": "F45",
    "fc44": "F44",
    "fc43": "F43",
}

TASK_STATES: dict[int, str] = {
    koji.TASK_STATES["FREE"]: "QUEUED",
    koji.TASK_STATES["OPEN"]: "BUILDING",
    koji.TASK_STATES["ASSIGNED"]: "BUILDING",
    koji.TASK_STATES["CLOSED"]: "COMPLETE",
    koji.TASK_STATES["FAILED"]: "FAILED",
    koji.TASK_STATES["CANCELED"]: "CANCELED",
}

# Retries after HTTP 403 rate limit errors (e.g. the GitHub API)
MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_FALLBACK_WAIT_SECONDS = 300

# Retries for transient Koji/Bodhi failures (e.g. the Koji proxy
# reconfiguring itself, dropped Bodhi connections)
MAX_KOJI_QUERY_RETRIES = 3
KOJI_QUERY_RETRY_DELAY_SECONDS = 5
MAX_BODHI_SAVE_ATTEMPTS = 5
BODHI_SAVE_RETRY_DELAY_SECONDS = 10

# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------


def run_cmd(
    cmd: list[str], input_data: str | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the CompletedProcess result."""
    env = dict(os.environ)
    result = subprocess.run(
        cmd,
        input=input_data,
        text=True,
        capture_output=True,
        env=env,
        check=check,
    )
    return result


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------


def setup_ssh_agent(ssh_key: str) -> None:
    """Start ssh-agent and add the given key."""
    ssh_key_path = Path(ssh_key).expanduser()

    if not ssh_key_path.exists():
        print(f"ERROR: SSH key not found at {ssh_key_path}", file=sys.stderr)
        sys.exit(1)

    # ssh-agent -s prints its export statements on stderr
    agent_result = run_cmd(["ssh-agent", "-s"])
    agent_output = (agent_result.stderr or agent_result.stdout).strip()
    print(f"SSH agent started: {agent_output}")

    env_vars = {}
    for line in agent_output.splitlines():
        match = re.match(r"(?P<var>\w+)=(?P<val>.+?);", line)
        if match:
            env_vars[match.group("var")] = match.group("val")

    if "SSH_AUTH_SOCK" not in env_vars or "SSH_AGENT_PID" not in env_vars:
        print("ERROR: Failed to parse ssh-agent output", file=sys.stderr)
        sys.exit(1)

    os.environ["SSH_AUTH_SOCK"] = env_vars["SSH_AUTH_SOCK"]
    os.environ["SSH_AGENT_PID"] = env_vars["SSH_AGENT_PID"]

    print(f"Adding SSH key: {ssh_key_path}")
    # ssh-add prompts for the passphrase on the terminal; run it with the
    # user's terminal attached so they can enter it manually.
    result = subprocess.run(["ssh-add", str(ssh_key_path)])

    if result.returncode != 0:
        print("ERROR: Failed to add SSH key", file=sys.stderr)
        sys.exit(1)

    print("SSH key added successfully")


def authenticate_kerberos(fk_user: str) -> None:
    """Authenticate with Kerberos using fkinit."""
    print(f"Authenticating with Kerberos as {fk_user}...")

    # fkinit prompts for the password (and optional OTP) on the terminal;
    # run it with the user's terminal attached so they can enter it
    # manually.
    result = subprocess.run(["fkinit", "-u", fk_user])

    if result.returncode != 0:
        print("ERROR: Kerberos authentication failed", file=sys.stderr)
        sys.exit(1)

    print("Kerberos authentication successful.")


# ---------------------------------------------------------------------------
# Side tag
# ---------------------------------------------------------------------------


def create_side_tag() -> str:
    """Request a new Fedora side tag via fedpkg and return the tag name."""
    print("Requesting a new side tag...")

    result = run_cmd(["fedpkg", "request-side-tag"], check=True)
    output = (result.stdout or "").strip()

    match = re.search(r"Side tag '([^']+)'", output)
    if not match:
        print(
            f"ERROR: Could not parse side tag from output:\n{output}",
            file=sys.stderr,
        )
        sys.exit(1)

    side_tag = match.group(1)
    print(f"Side tag created: {side_tag}")
    return side_tag


# ---------------------------------------------------------------------------
# Koji status helpers (internal utilities)
# ---------------------------------------------------------------------------


def _get_task_status(session: koji.ClientSession, build: KojiBuild) -> str:
    """Get human-readable task status for a build."""
    task_id = build.get("task_id")
    if not task_id:
        return "UNKNOWN"
    task = session.getTaskInfo(task_id)
    return TASK_STATES.get(task["state"], str(task["state"]))


def _compare_builds(a: KojiBuild, b: KojiBuild) -> int:
    """Compare two Koji builds using RPM version ordering."""
    return int(
        rpm.labelCompare(
            (str(a.get("epoch") or 0), a["version"], a["release"]),
            (str(b.get("epoch") or 0), b["version"], b["release"]),
        )
    )


def _newest_build(builds: list[KojiBuild]) -> KojiBuild:
    """Return the newest build from a list using RPM version ordering."""
    return max(builds, key=functools.cmp_to_key(_compare_builds))


def _branch_for_release(release: str) -> str | None:
    """Map a Koji build release string to a branch name."""
    for branch, marker in FEDORA_TAGS.items():
        if marker in release:
            return branch
    return None


def _version_matches(build: KojiBuild, expected_version: str) -> bool:
    """Check if a build's version matches the expected version string."""
    version: str = build["version"]
    return version == expected_version


def _status_color(status: str) -> str:
    """Return ANSI color code for a build status, or empty string for default."""
    if status == "FAILED":
        return "\033[91m"  # red
    if status == "BUILDING":
        return "\033[93m"  # yellow
    return ""


# ---------------------------------------------------------------------------
# Koji status display
# ---------------------------------------------------------------------------


def check_koji_status(
    packages: dict[str, str], expected_version: str | None = None
) -> None:
    """Use the Koji API to show per-Fedora-version build status for all cosmic packages.

    For each package, queries all builds by package ID and groups them by Fedora branch
    using RPM release markers (e.g. fc44). Finds the newest version across all branches
    and shows the build/task status for that version (or the latest available) in each branch.
    If expected_version is provided, it is used as the reference "latest" version instead.
    """
    client: koji.ClientSession = koji.ClientSession(KOJI_HUB)

    print()
    print(f"{'Package':<35}", end="")
    for branch in FEDORA_TAGS:
        print(f" {branch:<25}", end="")
    print()
    print("-" * (35 + 26 * len(FEDORA_TAGS)))

    for rpm_name in sorted(packages.keys()):
        try:
            package_id = client.getPackageID(rpm_name)
            if not package_id:
                print(f"{rpm_name:<35}", end="")
                for _ in FEDORA_TAGS:
                    print(f" {'N/A':<25}", end="")
                print()
                continue

            all_builds = client.listBuilds(
                packageID=package_id,
                queryOpts={"limit": 500},
            )

            if not all_builds:
                print(f"{rpm_name:<35}", end="")
                for _ in FEDORA_TAGS:
                    print(f" {'N/A':<25}", end="")
                print()
                continue

            branch_builds: dict[str, list[KojiBuild]] = {
                branch: [] for branch in FEDORA_TAGS
            }

            for build in all_builds:
                build_branch = _branch_for_release(build["release"])
                if build_branch:
                    branch_builds[build_branch].append(build)

            all_branch_builds = [b for builds in branch_builds.values() for b in builds]

            if not all_branch_builds:
                print(f"{rpm_name:<35}", end="")
                for _ in FEDORA_TAGS:
                    print(f" {'N/A':<25}", end="")
                print()
                continue

            latest = _newest_build(all_branch_builds)

            if expected_version:
                ref_version = expected_version
            else:
                ref_version = latest["version"]

            print(f"{rpm_name:<35}", end="")

            for branch in FEDORA_TAGS:
                builds = branch_builds[branch]

                if not builds:
                    print(f" {'N/A':<25}", end="")
                    continue

                matching = [b for b in builds if _compare_builds(b, latest) == 0]

                if matching:
                    build = _newest_build(matching)
                else:
                    build = _newest_build(builds)

                release_clean = (
                    build["release"]
                    .replace(".fc46", "")
                    .replace(".fc45", "")
                    .replace(".fc44", "")
                    .replace(".fc43", "")
                )
                version_str = f"{build['version']}-{release_clean}"
                status = _get_task_status(client, build)
                is_latest = _version_matches(build, ref_version)

                version_color = ""
                status_color = _status_color(status)
                reset = "\033[0m"

                if not is_latest:
                    version_color = "\033[91m"  # red

                if version_color or status_color:
                    print(
                        f" {version_color}{version_str}{reset} "
                        f"({status_color}{status}{reset})",
                        end="",
                    )
                else:
                    print(f" {version_str} ({status})", end="")

            print()
        except Exception as e:
            logger.error(f"Error checking {rpm_name}: {e}")
            print(f"{rpm_name:<35}", end="")
            for _ in FEDORA_TAGS:
                print(f" {'ERROR':<25}", end="")
            print()

    print()
    print(f"Queried {len(packages)} packages via Koji ({KOJI_HUB})")
    print()


def check_koji_status_for_package(
    package: str, packages: dict[str, str], expected_version: str | None = None
) -> None:
    """Check Koji status for a single package."""
    check_koji_status({package: packages[package]}, expected_version)


# ---------------------------------------------------------------------------
# Parsing / evaluation helpers
# ---------------------------------------------------------------------------


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def parse_koji_status(output: str) -> dict[str, dict[str, tuple[str, str]]]:
    """Parse the Koji status table output.

    Returns a dict mapping package name -> {branch: (version_str, status)}.
    Branches are like 'rawhide', 'f45', 'f44'.
    """
    packages = {}
    output = _strip_ansi(output)

    # One table column per branch, in FEDORA_TAGS order. The version
    # pattern tolerates a leftover "<version>-<release>.fcNN" string in
    # case the display forgot to strip the release marker.
    branches = [branch.lower() for branch in FEDORA_TAGS]
    column = r"([\d.]+-[\d.]+(?:\.fc\d+)?)\s+\((\w+)\)"
    line_pattern = re.compile(r"^(\S+)\s+" + r"\s+".join([column] * len(branches)))

    for line in output.splitlines():
        match = line_pattern.match(line)
        if match:
            packages[match.group(1)] = {
                branches[i]: (match.group(2 + i * 2), match.group(3 + i * 2))
                for i in range(len(branches))
            }

    return packages


def determine_expected_version(
    status: dict[str, dict[str, tuple[str, str]]],
) -> str | None:
    """Determine the expected version from the Koji status.

    Finds the most common version across all packages and branches.
    """
    versions = []
    for branches in status.values():
        for version_str, _ in branches.values():
            version = version_str.split("-")[0]
            versions.append(version)

    if not versions:
        return None

    from collections import Counter

    counter = Counter(versions)
    return counter.most_common(1)[0][0]


def evaluate_koji_status(
    output: str,
) -> str:
    """Evaluate the Koji status output and return one of:
    - 'complete': All packages are COMPLETE with the expected version.
    - 'building': Some packages are still BUILDING with the expected version.
    - 'error': Some packages have unexpected status or wrong version.
    """
    status = parse_koji_status(output)
    if not status:
        return "error"

    expected_version = determine_expected_version(status)
    if not expected_version:
        return "error"

    has_error = False
    has_building = False

    for pkg_name, branches in status.items():
        for branch, (version_str, task_status) in branches.items():
            version = version_str.split("-")[0]

            if task_status not in ("BUILDING", "COMPLETE"):
                has_error = True
            elif version != expected_version:
                has_error = True
            elif task_status == "BUILDING":
                has_building = True

    if has_error:
        return "error"
    elif has_building:
        return "building"
    else:
        return "complete"


# ---------------------------------------------------------------------------
# NVR collection for Bodhi
# ---------------------------------------------------------------------------


def get_completed_build_nvrs(
    packages: dict[str, str],
    expected_version: str | None = None,
) -> dict[str, list[str]]:
    """Query Koji for completed build NVRs, grouped by Fedora release.

    Returns a dict mapping release name (e.g. 'F44') to a list of NVR strings
    like ['cosmic-term-0.1.0-1.fc44', 'cosmic-applets-0.1.0-1.fc44', ...].
    Only includes builds whose task state is COMPLETE, and at most one
    build per package (the one with the newest release number), since a
    Bodhi update can only reference a single build per package.
    """
    client = __import__("koji").ClientSession(KOJI_HUB)
    # release name -> package name -> (release number, nvr) of newest build
    latest_builds: dict[str, dict[str, tuple[int, str]]] = {
        release: {} for release in FEDORA_RELEASES.values()
    }

    for rpm_name in sorted(packages.keys()):
        for attempt in range(1, MAX_KOJI_QUERY_RETRIES + 1):
            try:
                package_id = client.getPackageID(rpm_name)
                if not package_id:
                    break

                all_builds = client.listBuilds(
                    packageID=package_id,
                    queryOpts={"limit": 500},
                )

                for build in all_builds:
                    task_id = build.get("task_id")
                    if not task_id:
                        continue
                    task = client.getTaskInfo(task_id)
                    if task["state"] != __import__("koji").TASK_STATES["CLOSED"]:
                        continue

                    if expected_version and build["version"] != expected_version:
                        continue

                    release_str = build["release"]  # e.g. "2.fc45"
                    nvr = f"{build['name']}-{build['version']}-{release_str}"
                    release_num = int(re.split(r"\.", release_str)[0])
                    release_name = next(
                        (
                            name
                            for marker, name in FEDORA_RELEASES.items()
                            if marker in release_str
                        ),
                        release_str,
                    )

                    per_package = latest_builds.setdefault(release_name, {})
                    current = per_package.get(rpm_name)
                    if current is None or release_num > current[0]:
                        per_package[rpm_name] = (release_num, nvr)

                break
            except Exception as e:
                # E.g. "configuration error": the Koji proxy periodically
                # reloads its configuration and fails requests in that window.
                if attempt < MAX_KOJI_QUERY_RETRIES:
                    print(
                        f"  WARNING: Error querying Koji for {rpm_name} "
                        f"(attempt {attempt}/{MAX_KOJI_QUERY_RETRIES}): {e}. "
                        f"Retrying in {KOJI_QUERY_RETRY_DELAY_SECONDS}s...",
                        file=sys.stderr,
                    )
                    time.sleep(KOJI_QUERY_RETRY_DELAY_SECONDS)
                else:
                    print(
                        f"  WARNING: Error querying Koji for {rpm_name} "
                        f"after {attempt} attempts: {e}",
                        file=sys.stderr,
                    )

    return {
        release: sorted(nvr for _, nvr in per_package.values())
        for release, per_package in latest_builds.items()
    }


# ---------------------------------------------------------------------------
# Bodhi update creation
# ---------------------------------------------------------------------------


def _in_progress_updates_for(
    client: Any, release: str, nvrs: list[str]
) -> dict[str, dict[str, Any]]:
    """Find in-progress Bodhi updates containing any of the given builds.

    Returns a dict mapping alias -> {"builds": set of the given builds
    that are in that update, "status": the update status}. Only updates
    that are not finished (status pending, testing or unpushed) and
    belong to ``release`` are considered.
    """
    result: dict[str, dict[str, Any]] = {}
    try:
        query = client.query(builds=" ".join(nvrs))
    except Exception as e:
        print(
            f"    WARNING: Could not query existing {release} updates: {e}",
            file=sys.stderr,
        )
        return result
    wanted = set(nvrs)
    # The rawhide release is named after the branch (e.g. "F46"), not
    # "Rawhide"; older data may still use "rawhide". Everything else
    # matches case-insensitively.
    if release.lower() == "rawhide":
        release_names = {f"f{RAWHIDE_NUMBER}".lower(), "rawhide"}
    else:
        release_names = {release.lower()}
    for update in query.get("updates", []):
        if update["status"] not in ("pending", "testing", "unpushed"):
            continue
        if update["release"]["name"].lower() not in release_names:
            continue
        ours = {b["nvr"] for b in update["builds"]} & wanted
        if ours:
            result[update["alias"]] = {"builds": ours, "status": update["status"]}
    return result


def _save_bodhi_update(
    client: Any,
    release: str,
    nvrs: list[str],
    notes: str,
    existing_alias: str | None = None,
    from_tag: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Create (or extend) a Bodhi update, dropping builds that already have
    an update.

    If ``from_tag`` is given, the update is created from that Koji tag:
    the server pulls (and refreshes) the build list from the tag, so no
    builds are passed. Otherwise, if ``existing_alias`` is given, the
    existing update is edited and its build list is *replaced* by ``nvrs``,
    so the full list (existing builds plus new ones) must be passed, not
    just the new builds. Bodhi rejects the whole batch if even one build
    is already part of another update, so we retry with the offending
    builds removed.
    Returns (response, skipped_nvrs).
    """
    skipped: list[str] = []
    edited_kwarg = {"edited": existing_alias} if existing_alias else {}

    if from_tag:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = client.save(
                    from_tag=from_tag,
                    **edited_kwarg,
                    type="enhancement",
                    notes=notes,
                    request="testing",
                    autotime=True,
                    autokarma=True,
                    stable_karma=3,
                    unstable_karma=-3,
                    close_bugs=True,
                )
                return response, skipped
            except Exception as e:
                if attempt >= MAX_BODHI_SAVE_ATTEMPTS:
                    raise
                print(
                    f"    WARNING: Error saving {release} update "
                    f"(attempt {attempt}/{MAX_BODHI_SAVE_ATTEMPTS}): {e}. "
                    f"Retrying in {BODHI_SAVE_RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(BODHI_SAVE_RETRY_DELAY_SECONDS)

    remaining = list(nvrs)
    while remaining:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = client.save(
                    builds=remaining,
                    **edited_kwarg,
                    type="enhancement",
                    notes=notes,
                    request="testing",
                    autotime=True,
                    autokarma=True,
                    stable_karma=3,
                    unstable_karma=-3,
                    close_bugs=True,
                )
                return response, skipped
            except Exception as e:
                offending = [
                    nvr for nvr in remaining if f"for {nvr} already exists" in str(e)
                ]
                if offending:
                    skipped.extend(offending)
                    remaining = [nvr for nvr in remaining if nvr not in offending]
                    break
                if attempt >= MAX_BODHI_SAVE_ATTEMPTS:
                    raise
                # E.g. transient connection drops to the Bodhi server
                print(
                    f"    WARNING: Error saving {release} update "
                    f"(attempt {attempt}/{MAX_BODHI_SAVE_ATTEMPTS}): {e}. "
                    f"Retrying in {BODHI_SAVE_RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(BODHI_SAVE_RETRY_DELAY_SECONDS)

    return {}, skipped


def create_bodhi_updates(
    nvrs_by_release: dict[str, list[str]],
    notes: str | None = None,
    staging: bool = False,
    side_tag: str | None = None,
) -> None:
    """Create Bodhi updates for each release that has completed builds.

    Creates one Bodhi update per Fedora release, grouping all COSMIC
    package builds for that release together. The Rawhide update is
    created *from* the side tag the builds were made against, so the
    builds do not need the release build tag.
    """
    from bodhi.client.bindings import BodhiClient

    client = BodhiClient(staging=staging)
    instance = "staging" if staging else "production"

    created_updates: list[tuple[str, str]] = []

    for release, nvrs in sorted(nvrs_by_release.items()):
        if not nvrs:
            continue

        update_notes = notes or (
            f"Update COSMIC packages to latest version for {release}"
        )

        # Look for in-progress updates that already contain some of these
        # builds (e.g. created by a previous, interrupted run of this
        # pipeline) so that missing builds can be added to them instead of
        # creating another update.
        in_progress = _in_progress_updates_for(client, release, nvrs)
        for alias, info in in_progress.items():
            print(
                f"    {len(info['builds'])} build(s) already in in-progress "
                f"update {alias} (status: {info['status']})"
            )
        primary_alias = (
            max(in_progress, key=lambda a: len(in_progress[a]["builds"]))
            if in_progress
            else None
        )
        primary_info = in_progress[primary_alias] if primary_alias else None
        primary_builds = primary_info["builds"] if primary_info else set()
        missing = [nvr for nvr in nvrs if nvr not in primary_builds]

        # The Rawhide update is created *from* the side tag: the Bodhi
        # server pulls (and refreshes) the build list from the tag, so
        # the builds do not need the release build tag. (Bodhi names the
        # release "F46"; note RAWHIDE_BRANCH is the Koji tag "f46".)
        from_tag = side_tag if side_tag and release.lower() == "rawhide" else None

        if not missing:
            if primary_info is not None and primary_info["status"] == "unpushed":
                # The update was revoked (or never pushed): re-request it to
                # testing so the builds actually get released.
                print(
                    f"  Update {primary_alias} is unpushed (revoked or never "
                    f"pushed): re-requesting testing..."
                )
                try:
                    _save_bodhi_update(
                        client,
                        release,
                        sorted(primary_builds),
                        update_notes,
                        existing_alias=primary_alias,
                        from_tag=from_tag,
                    )
                except Exception as e:
                    print(
                        f"    ERROR re-requesting update {primary_alias}: {e}",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"    Nothing to do for {release}: all builds already in "
                    f"update {primary_alias}."
                )
            continue

        if from_tag:
            if primary_alias:
                print(
                    f"  Refreshing update {primary_alias} from side tag "
                    f"{from_tag} ({len(missing)} new build(s))..."
                )
            else:
                print(
                    f"  Creating {release} Bodhi update from side tag "
                    f"{from_tag} ({len(missing)} build(s))..."
                )
            builds_to_save = missing
        elif primary_alias:
            print(
                f"  Adding {len(missing)} build(s) to existing update "
                f"{primary_alias}..."
            )
            # Bodhi replaces the update's build list when editing it, so the
            # full set (existing builds plus the new ones) has to be passed
            # to keep the existing builds.
            builds_to_save = sorted(set(missing) | primary_builds)
        else:
            print(f"  Creating Bodhi update for {release} ({len(missing)} builds)...")
            builds_to_save = missing

        try:
            response, skipped = _save_bodhi_update(
                client,
                release,
                builds_to_save,
                update_notes,
                existing_alias=primary_alias,
                from_tag=from_tag,
            )
        except Exception as e:
            print(f"    ERROR creating update for {release}: {e}", file=sys.stderr)
            continue

        for nvr in skipped:
            print(f"    Skipping {nvr}: an update for it already exists")

        if not response:
            print(
                f"    Nothing to create for {release}: all builds already have updates."
            )
            continue

        alias = response["alias"]
        url = f"{client.base_url.rstrip('/')}/updates/{alias}"
        created_updates.append((release, alias))
        if primary_alias:
            print(f"    Added to update {alias}")
        else:
            print(f"    Update created: {response.get('title', alias)}")
        print(f"    Alias: {alias}")
        print(f"    URL:   {url}")

    if created_updates:
        print()
        print(f"  Created {len(created_updates)} Bodhi update(s) on {instance}.")
    else:
        print("  No updates created.")


# ---------------------------------------------------------------------------
# PackageBuilder (build logic from cosmic-packaging-new-release.py)
# ---------------------------------------------------------------------------


class PackageBuilder:
    def __init__(
        self, package: str, force_build: bool, dry_run: bool, working_directory: Path
    ) -> None:
        self.package = package
        self.force_build = force_build
        self.dry_run = dry_run
        self.working_directory = working_directory
        self.tag = PackageBuilder.get_latest_tag(self.package)
        logger.debug(f"[{self.package}]: Latest tag for package: {self.tag}")
        self.src_rpm = self.working_directory.joinpath(f"{self.package}.src.rpm")
        existing_rpms = glob.glob(
            str(self.working_directory.joinpath(f"{self.package}*.src.rpm"))
        )
        if not existing_rpms:
            self.version = PackageBuilder.download_package(
                self.package, self.src_rpm
            ).rsplit("-", maxsplit=1)[0]
            self.version = self.version.split(":", 1)[-1]
        elif existing_rpms[0]:
            try:
                logger.debug(
                    f"Found existing RPMS: {existing_rpms}. Choosing the one {existing_rpms[0]}"
                )
                rpm_file = Path(existing_rpms[0])
                self.version = rpm_file.name.removeprefix(
                    f"{self.package}-"
                ).removesuffix(".src.rpm")
                self.version = self.version.split("-", 1)[0]
                logger.debug(
                    f"Copying {rpm_file} -> {self.src_rpm}. Got version {self.version} from file."
                )
                rpm_file.copy(self.src_rpm)
            except Exception as e:
                raise Exception(
                    f"File {existing_rpms[0]} has invalid version info. Aborting."
                )
        else:
            raise Exception(f"File {existing_rpms[0]} has no version info. Aborting.")
        logger.debug(
            f"[{self.package}]: Latest built version for package: {self.version}"
        )
        self.repo_dir = self.working_directory.joinpath(self.package)
        self.commit_msg = f"Update to {self.version}"

    @staticmethod
    def get_latest_tag(package: str) -> str:
        repo_name = PACKAGES[package]
        url = f"https://api.github.com/repos/pop-os/{repo_name}/tags"
        with urlopen(url) as response:
            data = json.load(response)
            res: str = data[0]["name"].strip()
            return res.split("epoch-", 1)[1].replace("-", "~")

    @staticmethod
    def download_package(rpm_name: str, output_path: Path) -> str:
        url = f"https://copr.fedorainfracloud.org/api_3/package/?ownername=ryanabx&projectname=cosmic-epoch-tagged&packagename={rpm_name}&with_latest_succeeded_build=true"
        with requests.get(url) as response:
            data = response.json()
        source_package = data["builds"]["latest_succeeded"]["source_package"]["url"]
        version: str = data["builds"]["latest_succeeded"]["source_package"]["version"]

        logger.debug(f"[{rpm_name}]: Downloading {source_package} to {output_path}...")
        urlretrieve(source_package, output_path)
        return version

    def clone_fedpkg_repo(self) -> None:
        max_attempts = 5
        i = 0
        while not self.repo_dir.exists():
            if i >= max_attempts:
                raise Exception(f"{self.package}: Could not clone repo")
            try:
                subprocess.run(
                    ["fedpkg", "clone", self.package],
                    cwd=self.working_directory,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                logger.warning(
                    f"[{self.package}] Could not clone repo: {e} (Attempt {i}/{max_attempts})"
                )
            finally:
                i += 1
                time.sleep(0.5)

    def should_commit(self) -> bool:
        if self.force_build:
            return True
        old_commit_msg = subprocess.run(
            ["git", "-C", self.repo_dir, "log", "-1", "--pretty=%B"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout or ""
        return old_commit_msg.strip() != self.commit_msg

    def should_build(self, branch: str) -> bool:
        if self.force_build:
            return True
        check = subprocess.run(
            [
                "koji",
                "list-builds",
                f"--package={self.package}",
                "--state=COMPLETE",
                f"--pattern=*{self.version}-1.fc{PackageBuilder.branch_to_number(branch)}*",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        check2: subprocess.CompletedProcess[str] = subprocess.run(
            [
                "koji",
                "list-builds",
                f"--package={self.package}",
                "--state=BUILDING",
                f"--pattern=*{self.version}-1.fc{PackageBuilder.branch_to_number(branch)}*",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        currently_finished = (check.stdout or "").strip()
        currently_building = (check2.stdout or "").strip()
        if currently_finished != "":
            logger.info(
                f"[{self.package}, {branch}]: Found finished builds: {currently_finished.split('\n')}\n"
            )
        if currently_building != "":
            logger.info(
                f"[{self.package}, {branch}]: Found currently building builds: {currently_building.split('\n')}\n"
            )
        return (
            (check.stdout or "") == ""
            and (check2.stdout or "") == ""
            and (check.stderr or "") == ""
            and (check2.stderr or "") == ""
        )

    @staticmethod
    def branch_to_number(branch: str) -> str:
        return branch[1:] if branch != "rawhide" else RAWHIDE_NUMBER

    def build_branch(
        self, branch: str, side_tag: str, needs_build: bool | None = None
    ) -> bool:
        logger.debug(
            f"[{self.package}, {branch}]: Attempting to build branch {branch} for package {self.package}"
        )
        subprocess.run(
            ["fedpkg", "switch-branch", branch],
            cwd=self.repo_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.debug(f"[{self.package}, {branch}]: Checking if should commit...")
        if self.should_commit():
            if not self.dry_run:
                subprocess.run(
                    ["fedpkg", "import", "--skip-diffs", self.src_rpm],
                    cwd=self.repo_dir,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["fedpkg", "commit", "-m", self.commit_msg],
                    cwd=self.repo_dir,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                for _ in range(5):
                    try:
                        subprocess.run(
                            ["fedpkg", "push"],
                            cwd=self.repo_dir,
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        break
                    except Exception as exc:
                        logger.warning(
                            f"[{self.package}, {branch}]: fedpkg push failed: {exc}"
                        )
        else:
            logger.info(
                f"[{self.package}, {branch}]: Commit skipped. Commit messages matched."
            )
        logger.debug(f"[{self.package}, {branch}]: Checking if should build...")
        if needs_build is None:
            needs_build = self.should_build(branch)
        if needs_build:
            if not self.dry_run:
                if side_tag and branch in SIDE_TAG_BRANCHES:
                    try:
                        subprocess.run(
                            ["fedpkg", "build", f"--target={side_tag}"],
                            cwd=self.repo_dir,
                            timeout=10,
                            capture_output=True,
                            check=False,
                        )
                    except subprocess.TimeoutExpired:
                        logger.info(
                            f"[{self.package}, {branch}]: Building version {branch}\n"
                        )
                    return True
                else:
                    try:
                        subprocess.run(
                            ["fedpkg", "build"],
                            cwd=self.repo_dir,
                            timeout=10,
                            capture_output=True,
                            check=False,
                        )
                    except subprocess.TimeoutExpired:
                        logger.info(
                            f"[{self.package}, {branch}]: Building version {branch}\n"
                        )
                    return True
            else:
                logger.info(f"[{self.package}, {branch}]: Dry run - would build\n")
                return True
        else:
            logger.info(
                f"[{self.package}, {branch}]: Build skipped. A build was found with matching version {self.version}\n"
            )
            return False

    def build_with_side_tag(self, side_tag: str) -> bool:
        did_build_anything = False
        for br in FEDORA_BRANCHES:
            if br == "all":
                continue
            # Partial rebuild: skip branches where the expected version is
            # already COMPLETE or BUILDING in Koji
            if not self.should_build(br):
                logger.info(
                    f"[{self.package}]: {br} skipped: {self.version} is already "
                    "COMPLETE or BUILDING in Koji"
                )
                continue
            try:
                built_package = self.build_branch(br, side_tag, needs_build=True)
                did_build_anything = did_build_anything or built_package
            except Exception as e:
                if _is_rate_limit_error(e):
                    raise
                logger.error(f"[{self.package}, {br}]: Error({br}): {e}\n")
        return did_build_anything


# ---------------------------------------------------------------------------
# Single-package iteration
# ---------------------------------------------------------------------------


def _is_rate_limit_error(exc: Exception) -> bool:
    """True if the exception looks like an HTTP 403 rate limit error."""
    return "403" in str(exc) and "rate limit" in str(exc).lower()


def _rate_limit_wait_time(exc: Exception) -> float:
    """Seconds to wait before retrying after a rate limit error.

    Uses the reset time advertised by the API when available (GitHub sends
    ``X-RateLimit-Reset`` as a Unix timestamp, some APIs send
    ``Retry-After`` as a delay), otherwise falls back to a fixed delay.
    """
    headers = getattr(exc, "headers", None)
    if headers:
        try:
            reset = headers.get("X-RateLimit-Reset")
            if reset:
                return max(10.0, float(reset) - time.time())
            retry_after = headers.get("Retry-After")
            if retry_after:
                return max(10.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    return float(RATE_LIMIT_FALLBACK_WAIT_SECONDS)


def run_iteration(
    rpm_name: str,
    force_build: bool,
    side_tag: str,
    dry_run: bool,
    workdir: Path,
) -> None:
    """Run one package's build, retrying after HTTP 403 rate limit errors.

    Retries are partial rebuilds: branches whose expected version is already
    COMPLETE or BUILDING in Koji are skipped via ``should_build``.
    """
    for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 1):
        try:
            _run_iteration_once(rpm_name, force_build, side_tag, dry_run, workdir)
            return
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < MAX_RATE_LIMIT_RETRIES:
                wait = _rate_limit_wait_time(e)
                logger.warning(
                    f"[{rpm_name}]: Rate limit exceeded "
                    f"(attempt {attempt}/{MAX_RATE_LIMIT_RETRIES}). "
                    f"Waiting {wait:.0f}s before retrying..."
                )
                time.sleep(wait)
                continue
            logger.error(f"[{rpm_name}]: Failed to run iteration: {e}")
            return


def _run_iteration_once(
    rpm_name: str,
    force_build: bool,
    side_tag: str,
    dry_run: bool,
    workdir: Path,
) -> None:
    # Note: exceptions (e.g. rate limit errors) are intentionally
    # re-raised so that run_iteration can wait and retry the iteration.
    working_directory = workdir
    Path.mkdir(working_directory, exist_ok=True, parents=True)
    logger.debug(working_directory)
    pkg = PackageBuilder(rpm_name, force_build, dry_run, working_directory)

    if pkg.tag == "":
        logger.error(
            f"[{pkg.package}]: Could not get latest tag from https://github.com/pop-os/{PACKAGES[rpm_name]}"
        )
        return

    if pkg.version != pkg.tag:
        logger.error(
            f"[{pkg.package}]: Latest version does not equal the latest tag. Aborting"
        )
        return
    pkg.clone_fedpkg_repo()

    time_before = datetime.datetime.now(datetime.timezone.utc)
    did_build_anything = pkg.build_with_side_tag(side_tag)
    time_after = datetime.datetime.now(datetime.timezone.utc)

    elapsed = time_after - time_before
    logger.info(f"[{pkg.package}]: === Done in {elapsed} seconds ===\n")

    if not did_build_anything:
        logger.info(f"[{pkg.package}]: {rpm_name}: Nothing was rebuilt.")


# ---------------------------------------------------------------------------
# Build execution helpers
# ---------------------------------------------------------------------------


def build_package(
    package: str, force_build: bool, workdir: Path, side_tag: str, dry_run: bool
) -> None:
    working_directory = workdir.joinpath(package)
    try:
        logger.debug(f"[{package}]: Building package {package}")
        run_iteration(package, force_build, side_tag, dry_run, working_directory)
        logger.debug(f"[{package}]: Done building package {package}")
    finally:
        shutil.rmtree(working_directory)


def run_builds(
    target_packages: dict[str, str],
    side_tag: str,
    force_map: dict[str, bool] | None = None,
    dry_run: bool = False,
) -> None:
    """Queue builds for the given packages using the side tag.

    ``force_map`` lists packages that must be rebuilt even if a build with
    the expected version is already BUILDING or COMPLETE.
    """
    if not target_packages:
        logger.info("No packages need building.")
        return
    force_map = force_map or {}

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        with ThreadPoolExecutor() as executor:
            futures = []
            for pkg_name in target_packages:
                futures.append(
                    executor.submit(
                        build_package,
                        pkg_name,
                        force_map.get(pkg_name, False),
                        workdir,
                        side_tag,
                        dry_run,
                    )
                )
            for future in futures:
                future.result()


def _packages_needing_builds(
    status: dict[str, dict[str, tuple[str, str]]],
    packages: dict[str, str],
    expected_version: str | None,
) -> dict[str, str]:
    """Return the packages that still need (re)building.

    A package needs building unless every tracked branch already has a
    BUILDING or COMPLETE build at the expected version. Packages missing
    from ``status`` (e.g. never built) always need building.
    """
    needed: dict[str, str] = {}
    for pkg_name, package in packages.items():
        branches = status.get(pkg_name)
        if branches is None:
            needed[pkg_name] = package
            continue
        all_building_or_complete = all(
            version_str.split("-")[0] == expected_version
            and task_status in ("BUILDING", "COMPLETE")
            for version_str, task_status in branches.values()
        )
        if not all_building_or_complete:
            needed[pkg_name] = package
    return needed


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cosmic-packaging-automation",
        description="Full automated pipeline for Fedora COSMIC packaging: "
        "SSH/Kerberos setup, side tag creation, build queuing, "
        "Koji monitoring, and Bodhi update submission.",
    )

    # Authentication
    parser.add_argument(
        "--ssh-key",
        help="Path to the SSH key (e.g., ~/.ssh/id_ed25519)",
    )
    parser.add_argument(
        "--fk-user",
        help="Kerberos (FAS) username to log in with",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip SSH agent and Kerberos authentication setup. "
        "If specified, --ssh-key and --fk-user are not required.",
    )

    # Build options
    parser.add_argument(
        "--side-tag",
        help="Use this fedpkg side tag instead of generating one",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate commits/pushes without actually performing them",
    )
    parser.add_argument(
        "--force-package",
        action="append",
        help="Force update/build package",
        choices=list(PACKAGES.keys()),
    )
    parser.add_argument(
        "--rpm_name",
        help="Name of the RPM to build (defaults to all of them)",
        choices=list(PACKAGES.keys()),
    )

    # Monitoring
    parser.add_argument(
        "--koji-wait-time",
        type=int,
        default=5,
        help="Time in minutes to wait between Koji status checks (default: 10)",
    )

    # Bodhi
    parser.add_argument(
        "--bodhi",
        action="store_true",
        help="After Koji builds complete, create Bodhi updates for each Fedora release",
    )
    parser.add_argument(
        "--bodhi-notes",
        help="Custom notes for Bodhi updates (default: auto-generated from version)",
    )
    parser.add_argument(
        "--bodhi-staging",
        action="store_true",
        help="Use the Bodhi staging instance for update submission",
    )

    # Koji status display (standalone)
    parser.add_argument(
        "--koji-status",
        action="store_true",
        help="Show all cosmic packages with per-Fedora-version build status (fc43/fc44/fc45/fc46). "
        "Highlights non-latest versions and non-COMPLETE statuses.",
    )
    parser.add_argument(
        "--koji-package",
        help="Show Koji status for a specific package (requires --koji-status)",
        choices=list(PACKAGES.keys()),
    )
    parser.add_argument(
        "--latest-version",
        help="Specify the expected latest version (defaults to highest version found in Koji)",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Standalone Koji status mode
    # ------------------------------------------------------------------
    if args.koji_status:
        if args.koji_package:
            check_koji_status_for_package(
                args.koji_package, PACKAGES, args.latest_version
            )
        else:
            check_koji_status(PACKAGES, args.latest_version)
        sys.exit(0)

    # ------------------------------------------------------------------
    # Validate required args when not skipping setup
    # ------------------------------------------------------------------
    if not args.skip_setup:
        missing = []
        if not args.ssh_key:
            missing.append("--ssh-key")
        if not args.fk_user:
            missing.append("--fk-user")

        if missing:
            print(
                f"ERROR: When --skip-setup is not specified, the following arguments are required: "
                f"{', '.join(missing)}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Determine which packages to force-build
    force_map: dict[str, bool] = {}
    if args.force_package:
        for pkg in args.force_package:
            force_map[pkg] = True
    if args.rpm_name:
        force_map[args.rpm_name] = True

    # The set of packages this run is responsible for
    if args.rpm_name:
        scoped_packages = {args.rpm_name: PACKAGES[args.rpm_name]}
    else:
        scoped_packages = PACKAGES

    # ------------------------------------------------------------------
    # Step 1 & 2: Setup (SSH agent + Kerberos)
    # ------------------------------------------------------------------
    if not args.skip_setup:
        print("=" * 60)
        print("Step 1: Setting up SSH agent...")
        print("=" * 60)
        setup_ssh_agent(args.ssh_key)

        print()
        print("=" * 60)
        print("Step 2: Authenticating with Kerberos...")
        print("=" * 60)
        authenticate_kerberos(args.fk_user)
        print()

    # ------------------------------------------------------------------
    # Step 3: Create side tag
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Step 3: Creating side tag...")
    print("=" * 60)
    if args.side_tag:
        side_tag = args.side_tag
        print(f"Using provided side tag: {side_tag}")
    else:
        side_tag = create_side_tag()
    print()

    # ------------------------------------------------------------------
    # Step 4: Build & monitor loop
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Step 4: Building packages & monitoring Koji status...")
    print("=" * 60)
    wait_seconds = args.koji_wait_time * 60
    max_koji_checks = 100

    for check_num in range(1, max_koji_checks + 1):
        print(f"\n--- Koji status check #{check_num} ---")

        # Check Koji status once; capture the output so it can be
        # displayed and parsed in the same pass.
        status_buffer = io.StringIO()
        with contextlib.redirect_stdout(status_buffer):
            check_koji_status(PACKAGES, args.latest_version)
        status_output = status_buffer.getvalue()
        print(status_output)

        result = evaluate_koji_status(status_output)

        if result == "complete":
            expected_version = determine_expected_version(
                parse_koji_status(status_output)
            )

            print()
            print("=" * 60)
            print("SUCCESS: All packages are COMPLETE!")
            print("=" * 60)

            # Step 5: Submit to Bodhi (optional)
            if args.bodhi:
                print()
                print("=" * 60)
                print("Step 5: Creating Bodhi updates...")
                print("=" * 60)
                nvrs_by_release = get_completed_build_nvrs(PACKAGES, expected_version)

                for release, nvrs in sorted(nvrs_by_release.items()):
                    if nvrs:
                        print(f"  {release}: {len(nvrs)} build(s)")
                        for nvr in nvrs:
                            print(f"    - {nvr}")
                print()

                create_bodhi_updates(
                    nvrs_by_release,
                    notes=args.bodhi_notes,
                    staging=args.bodhi_staging,
                    side_tag=side_tag,
                )

            sys.exit(0)

        # Queue builds for packages that are NOT in BUILDING or COMPLETE
        # at the target version
        status = parse_koji_status(status_output)
        expected_version = args.latest_version or determine_expected_version(status)
        packages_to_build = _packages_needing_builds(
            status, scoped_packages, expected_version
        )
        if packages_to_build:
            print(
                f"Queuing builds for {len(packages_to_build)} package(s) not yet "
                f"BUILDING/COMPLETE at {expected_version}:"
            )
            for pkg_name in sorted(packages_to_build):
                print(f"  - {pkg_name}")
            run_builds(packages_to_build, side_tag, force_map, args.dry_run)
        else:
            print(
                "Nothing to queue: no scoped package is missing a BUILDING/COMPLETE "
                "build at the target version."
            )

        print(f"Waiting {args.koji_wait_time} minutes before next check...")
        time.sleep(wait_seconds)

    print(
        f"ERROR: Max Koji checks ({max_koji_checks}) reached without completion.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
