"""Full automated pipeline for the Fedora COSMIC packaging workflow.

Handles the complete lifecycle:
  1. SSH agent setup & Kerberos authentication
  2. Side tag creation in Koji
  3. Building packages via COPR-sourced SRPMs into Koji (with side tags)
  4. Monitoring Koji build status until all packages complete
  5. Optionally creating Bodhi updates for each Fedora release
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
from urllib.request import urlopen, urlretrieve

import koji
import requests
import rpm
from cosmic_common import (
    FEDORA_BRANCHES,
    PACKAGES,
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

FEDORA_TAGS = {
    "Rawhide": "fc45",
    "F44": "fc44",
    "F43": "fc43",
}

FEDORA_RELEASES = {
    "fc45": "Rawhide",
    "fc44": "F44",
    "fc43": "F43",
}

TASK_STATES = {
    koji.TASK_STATES["FREE"]: "QUEUED",
    koji.TASK_STATES["OPEN"]: "BUILDING",
    koji.TASK_STATES["ASSIGNED"]: "BUILDING",
    koji.TASK_STATES["CLOSED"]: "COMPLETE",
    koji.TASK_STATES["FAILED"]: "FAILED",
    koji.TASK_STATES["CANCELED"]: "CANCELED",
}

# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------


def run_cmd(
    cmd: list[str], input_data: str | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the CompletedProcess result."""
    env = dict(os.environ)
    result = subprocess.run(
        cmd,
        input=input_data,
        text=True,
        env=env,
        check=check,
    )
    return result


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------


def setup_ssh_agent(ssh_key: str, ssh_password: str) -> None:
    """Start ssh-agent and add the given key."""
    ssh_key_path = Path(ssh_key).expanduser()

    if not ssh_key_path.exists():
        print(f"ERROR: SSH key not found at {ssh_key_path}", file=sys.stderr)
        sys.exit(1)

    agent_output = run_cmd(["ssh-agent", "-s"]).stdout.strip()
    print(f"SSH agent started: {agent_output}")

    env_vars = {}
    for line in agent_output.splitlines():
        match = re.match(r'export (\w+)="(.+)"', line)
        if match:
            env_vars[match.group(1)] = match.group(2)

    if "SSH_AUTH_SOCK" not in env_vars or "SSH_AGENT_PID" not in env_vars:
        print("ERROR: Failed to parse ssh-agent output", file=sys.stderr)
        sys.exit(1)

    os.environ["SSH_AUTH_SOCK"] = env_vars["SSH_AUTH_SOCK"]
    os.environ["SSH_AGENT_PID"] = env_vars["SSH_AGENT_PID"]

    print(f"Adding SSH key: {ssh_key_path}")
    result = subprocess.run(
        ["ssh-add", str(ssh_key_path)],
        input=ssh_password + "\n",
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        print(f"ERROR: Failed to add SSH key: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    print(f"SSH key added successfully: {result.stdout.strip()}")


def authenticate_kerberos(fk_user: str, fk_password: str) -> None:
    """Authenticate with Kerberos using fkinit."""
    print(f"Authenticating with Kerberos as {fk_user}...")

    result = subprocess.run(
        ["fkinit", "-u", fk_user],
        input=fk_password + "\n",
        text=True,
        capture_output=True,
        check=False,
    )

    combined_output = result.stdout + result.stderr

    if result.returncode != 0 or "Ticket cache:" not in combined_output:
        print(
            f"ERROR: Kerberos authentication failed.\nOutput:\n{combined_output}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Kerberos authentication successful.")


# ---------------------------------------------------------------------------
# Side tag
# ---------------------------------------------------------------------------


def create_side_tag() -> str:
    """Request a new Fedora side tag via fedpkg and return the tag name."""
    print("Requesting a new side tag...")

    result = run_cmd(["fedpkg", "request-side-tag"], check=True)
    output = result.stdout.strip()

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


def _get_task_status(session, build):
    """Get human-readable task status for a build."""
    task_id = build.get("task_id")
    if not task_id:
        return "UNKNOWN"
    task = session.getTaskInfo(task_id)
    return TASK_STATES.get(task["state"], str(task["state"]))


def _compare_builds(a, b):
    """Compare two Koji builds using RPM version ordering."""
    return rpm.labelCompare(  # type: ignore[no-any-return]
        (str(a.get("epoch") or 0), a["version"], a["release"]),
        (str(b.get("epoch") or 0), b["version"], b["release"]),
    )


def _newest_build(builds):
    """Return the newest build from a list using RPM version ordering."""
    return max(builds, key=functools.cmp_to_key(_compare_builds))


def _branch_for_release(release):
    """Map a Koji build release string to a branch name."""
    for branch, marker in FEDORA_TAGS.items():
        if marker in release:
            return branch
    return None


def _version_matches(build, expected_version):
    """Check if a build's version matches the expected version string."""
    return build["version"] == expected_version


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

            branch_builds: dict[str, list[dict]] = {
                branch: [] for branch in FEDORA_TAGS
            }

            for build in all_builds:
                branch = _branch_for_release(build["release"])
                if branch:
                    branch_builds[branch].append(build)

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
    Branches are like 'rawhide', 'f44', 'f43'.
    """
    packages = {}
    output = _strip_ansi(output)

    line_pattern = re.compile(
        r"^(\S+)\s+"
        r"([\d.]+-[\d.]+)\s+\((\w+)\)\s+"
        r"([\d.]+-[\d.]+)\s+\((\w+)\)\s+"
        r"([\d.]+-[\d.]+)\s+\((\w+)\)"
    )

    for line in output.splitlines():
        match = line_pattern.match(line)
        if match:
            pkg_name = match.group(1)
            packages[pkg_name] = {
                "rawhide": (match.group(2), match.group(3)),
                "f44": (match.group(4), match.group(5)),
                "f43": (match.group(6), match.group(7)),
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
    Only includes builds whose task state is COMPLETE.
    """
    client = __import__("koji").ClientSession(KOJI_HUB)
    nvrs_by_release: dict[str, list[str]] = {
        release: [] for release in FEDORA_RELEASES.values()
    }

    for rpm_name in sorted(packages.keys()):
        try:
            package_id = client.getPackageID(rpm_name)
            if not package_id:
                continue

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

                release_str = build["release"]
                matched = False
                for marker, release_name in FEDORA_RELEASES.items():
                    if marker in release_str:
                        nvr = f"{build['name']}-{build['version']}-{build['release']}"
                        nvrs_by_release[release_name].append(nvr)
                        matched = True
                        break

                if not matched:
                    nvr = f"{build['name']}-{build['version']}-{build['release']}"
                    nvrs_by_release[release_str] = nvrs_by_release.get(release_str, [])
                    nvrs_by_release[release_str].append(nvr)

        except Exception as e:
            print(
                f"  WARNING: Error querying Koji for {rpm_name}: {e}", file=sys.stderr
            )

    return nvrs_by_release


# ---------------------------------------------------------------------------
# Bodhi update creation
# ---------------------------------------------------------------------------


def create_bodhi_updates(
    nvrs_by_release: dict[str, list[str]],
    notes: str | None = None,
    staging: bool = False,
) -> None:
    """Create Bodhi updates for each release that has completed builds.

    Creates one Bodhi update per Fedora release, grouping all COSMIC
    package builds for that release together.
    """
    from bodhi.client.bindings import BodhiClient

    client = BodhiClient(staging=staging)
    instance = "staging" if staging else "production"

    created_updates: list[tuple[str, str]] = []

    for release, nvrs in sorted(nvrs_by_release.items()):
        if not nvrs:
            continue

        print(f"  Creating Bodhi update for {release} ({len(nvrs)} builds)...")

        if not notes:
            notes = f"Update COSMIC packages to latest version for {release}"

        try:
            response = client.save(
                builds=nvrs,
                type="enhancement",
                notes=notes,
                request="testing",
                autotime=True,
                autokarma=True,
                stable_karma=3,
                unstable_karma=-3,
                close_bugs=True,
            )

            alias = response["alias"]
            title = response.get("title", alias)
            url = client.base_url.rstrip("/") + f"updates/{alias}"
            created_updates.append((release, alias))
            print(f"    Update created: {title}")
            print(f"    Alias: {alias}")
            print(f"    URL:   {url}")

        except Exception as e:
            print(f"    ERROR creating update for {release}: {e}", file=sys.stderr)

    if created_updates:
        print()
        print(f"  Created {len(created_updates)} Bodhi update(s) on {instance}.")
    else:
        print("  No updates created (no completed builds found).")


# ---------------------------------------------------------------------------
# PackageBuilder (build logic from cosmic-packaging-new-release.py)
# ---------------------------------------------------------------------------


class PackageBuilder:
    def __init__(
        self, package: str, force_build: bool, dry_run: bool, working_directory: Path
    ):
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

        logger.debug(f"[{rpm_name}]: Downloading {source_package} to {output_path}...")
        urlretrieve(source_package, output_path)
        return data["builds"]["latest_succeeded"]["source_package"]["version"]

    def clone_fedpkg_repo(self):
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
        ).stdout.strip()
        return old_commit_msg != self.commit_msg

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
        check2 = subprocess.run(
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
        currently_finished = check.stdout.strip()
        currently_building = check2.stdout.strip()
        if currently_finished != "":
            logger.info(
                f"[{self.package}, {branch}]: Found finished builds: {currently_finished.split('\n')}\n"
            )
        if currently_building != "":
            logger.info(
                f"[{self.package}, {branch}]: Found currently building builds: {currently_building.split('\n')}\n"
            )
        return (
            check.stdout.strip() == ""
            and check2.stdout.strip() == ""
            and check.stderr.strip() == ""
            and check2.stderr.strip() == ""
        )

    @staticmethod
    def branch_to_number(branch: str) -> str:
        return branch[1:] if branch != "rawhide" else RAWHIDE_NUMBER

    def build_branch(self, branch: str, side_tag: str) -> bool:
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
        if self.should_build(branch):
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
        errored_local = []
        for br in FEDORA_BRANCHES:
            if br == "all":
                continue
            try:
                built_package = self.build_branch(br, side_tag)
                did_build_anything = did_build_anything or built_package
            except Exception as e:
                logger.error(f"[{self.package}, {br}]: Error({br}): {e}\n")
                errored_local.append(f"[{self.package} {br}]")
        return did_build_anything


# ---------------------------------------------------------------------------
# Single-package iteration
# ---------------------------------------------------------------------------


def run_iteration(
    rpm_name: str,
    force_build: bool,
    side_tag: str,
    dry_run: bool,
    workdir: Path,
):
    errored = []
    try:
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
    except Exception as e:
        logger.error(f"[{rpm_name}]: Failed to run iteration: {e}")
        errored.append(f"{rpm_name} all")


# ---------------------------------------------------------------------------
# Build execution helpers
# ---------------------------------------------------------------------------


def build_package(
    package: str, force_build: bool, workdir: Path, side_tag: str, dry_run: bool
):
    working_directory = workdir.joinpath(package)
    try:
        logger.debug(f"[{package}]: Building package {package}")
        run_iteration(package, force_build, side_tag, dry_run, working_directory)
        logger.debug(f"[{package}]: Done building package {package}")
    finally:
        shutil.rmtree(working_directory)


def run_builds(
    packages: dict[str, str],
    side_tag: str,
    force_build: bool = False,
    dry_run: bool = False,
    rpm_name: str | None = None,
) -> None:
    """Run builds for one or all COSMIC packages using the side tag."""
    if rpm_name:
        target_packages = {rpm_name: packages[rpm_name]}
    else:
        target_packages = packages

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        with ThreadPoolExecutor() as executor:
            futures = []
            for pkg_name in target_packages:
                force = force_build or (rpm_name is not None and pkg_name == rpm_name)
                futures.append(
                    executor.submit(
                        build_package, pkg_name, force, workdir, side_tag, dry_run
                    )
                )
            for future in futures:
                future.result()


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
        "--ssh-password",
        help="Password for the SSH key",
    )
    parser.add_argument(
        "--fk-user",
        help="Kerberos (FAS) username to log in with",
    )
    parser.add_argument(
        "--fk-password",
        help="Kerberos (FAS) password",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip SSH agent and Kerberos authentication setup. "
        "If specified, --ssh-key, --ssh-password, --fk-user, and --fk-password are not required.",
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
        "--error-wait-time",
        type=int,
        default=5,
        help="Time in minutes to wait before retrying on errors (default: 5)",
    )
    parser.add_argument(
        "--koji-wait-time",
        type=int,
        default=10,
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
        help="Show all cosmic packages with per-Fedora-version build status (fc43/fc44/fc45). "
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
        if not args.ssh_password:
            missing.append("--ssh-password")
        if not args.fk_user:
            missing.append("--fk-user")
        if not args.fk_password:
            missing.append("--fk-password")

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

    # ------------------------------------------------------------------
    # Step 1 & 2: Setup (SSH agent + Kerberos)
    # ------------------------------------------------------------------
    if not args.skip_setup:
        print("=" * 60)
        print("Step 1: Setting up SSH agent...")
        print("=" * 60)
        setup_ssh_agent(args.ssh_key, args.ssh_password)

        print()
        print("=" * 60)
        print("Step 2: Authenticating with Kerberos...")
        print("=" * 60)
        authenticate_kerberos(args.fk_user, args.fk_password)
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
    # Step 4: Build packages
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Step 4: Building packages...")
    print("=" * 60)
    run_builds(
        PACKAGES,
        side_tag,
        force_build=bool(args.force_package),
        dry_run=args.dry_run,
        rpm_name=args.rpm_name,
    )
    print()

    # ------------------------------------------------------------------
    # Step 5: Monitor Koji status
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Step 5: Monitoring Koji build status...")
    print("=" * 60)
    wait_minutes = args.koji_wait_time
    wait_seconds = wait_minutes * 60
    max_koji_checks = 100

    for check_num in range(1, max_koji_checks + 1):
        print(f"\n--- Koji status check #{check_num} ---")
        check_koji_status(PACKAGES, args.latest_version)

        # Capture output for parsing
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            check_koji_status(PACKAGES, args.latest_version)
        parse_output = f.getvalue()

        result = evaluate_koji_status(parse_output)

        if result == "complete":
            expected_version = determine_expected_version(
                parse_koji_status(parse_output)
            )

            print()
            print("=" * 60)
            print("SUCCESS: All packages are COMPLETE!")
            print("=" * 60)

            # Step 6: Submit to Bodhi (optional)
            if args.bodhi:
                print()
                print("=" * 60)
                print("Step 6: Creating Bodhi updates...")
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
                )

            sys.exit(0)
        elif result == "building":
            print(
                f"Some packages are still building. "
                f"Waiting {wait_minutes} minutes before next check..."
            )
            time.sleep(wait_seconds)
        else:
            print(
                "Packages detected with unexpected status or wrong version. "
                "Re-running builds..."
            )
            run_builds(
                PACKAGES,
                side_tag,
                force_build=True,
                dry_run=args.dry_run,
                rpm_name=args.rpm_name,
            )
            time.sleep(wait_seconds)

    print(
        f"ERROR: Max Koji checks ({max_koji_checks}) reached without completion.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
