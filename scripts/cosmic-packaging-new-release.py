import argparse
import datetime
import functools
import json
import logging
import shutil
import subprocess
import time
from http.client import HTTPResponse
from pathlib import Path
from typing import cast
from urllib.request import urlopen, urlretrieve

import koji
import requests
import rpm

logger = logging.getLogger(__name__)
logging.basicConfig(
    handlers=[
        logging.FileHandler("cosmic-packaging-new-release.log"),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)

import glob

from cosmic_common import FEDORA_BRANCHES, PACKAGES, RAWHIDE_BRANCH, SIDE_TAG_BRANCHES

builds = []
errored = []

KOJI_HUB = "https://koji.fedoraproject.org/kojihub"

# Fedora release markers used in Koji build release strings (e.g. "1.fc46")
FEDORA_TAGS = {
    "Rawhide": "fc46",
    "F45": "fc45",
    "F44": "fc44",
    "F43": "fc43",
}


TASK_STATES = {
    koji.TASK_STATES["FREE"]: "QUEUED",
    koji.TASK_STATES["OPEN"]: "BUILDING",
    koji.TASK_STATES["ASSIGNED"]: "BUILDING",
    koji.TASK_STATES["CLOSED"]: "COMPLETE",
    koji.TASK_STATES["FAILED"]: "FAILED",
    koji.TASK_STATES["CANCELED"]: "CANCELED",
}


def _get_task_status(session, build):
    """Get human-readable task status for a build."""
    task_id = build.get("task_id")
    if not task_id:
        return "UNKNOWN"
    task = session.getTaskInfo(task_id)
    return TASK_STATES.get(task["state"], str(task["state"]))


def _compare_builds(a, b):
    """Compare two Koji builds using RPM version ordering."""
    return rpm.labelCompare(
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

            # Get all builds for this package
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

            # Group builds by branch using release field
            branch_builds: dict[str, list[dict]] = {
                branch: [] for branch in FEDORA_TAGS
            }

            for build in all_builds:
                branch = _branch_for_release(build["release"])
                if branch:
                    branch_builds[branch].append(build)

            # Find newest version across all branches
            all_branch_builds = [b for builds in branch_builds.values() for b in builds]

            if not all_branch_builds:
                print(f"{rpm_name:<35}", end="")
                for _ in FEDORA_TAGS:
                    print(f" {'N/A':<25}", end="")
                print()
                continue

            latest = _newest_build(all_branch_builds)

            # Determine the reference version for coloring
            if expected_version:
                ref_version = expected_version
            else:
                ref_version = latest["version"]

            # Print row
            print(f"{rpm_name:<35}", end="")

            for branch in FEDORA_TAGS:
                builds = branch_builds[branch]

                if not builds:
                    print(f" {'N/A':<25}", end="")
                    continue

                # Prefer the global newest version if this branch has it
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

                # Apply colors
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
        if not existing_rpms:  # Download package
            # Download src rpm, and return the version
            # Remove any build numbers at the end i.e. 1.0.0~beta.8"-1"
            self.version = PackageBuilder.download_package(
                self.package, self.src_rpm
            ).rsplit("-", maxsplit=1)[0]
            self.version = self.version.split(":", 1)[-1]
        elif existing_rpms[0]:  # We have an RPM already built or downloaded
            try:
                logger.debug(
                    f"Found existing RPMS: {existing_rpms}. Choosing the one {existing_rpms[0]}"
                )
                rpm_file = Path(existing_rpms[0])
                self.version = rpm_file.name.removeprefix(
                    f"{self.package}-"
                ).removesuffix(
                    ".src.rpm"
                )  # For example, cosmic-app-library-1.0.8-1.fc45.src.rpm -> 1.0.8-1.fc45
                self.version = self.version.split("-", 1)[0]  # 1.0.8-1.fc45 -> 1.0.8
                logger.debug(
                    f"Copying {rpm_file} -> {self.src_rpm}. Got version {self.version} from file."
                )
                rpm_file.copy(
                    self.src_rpm
                )  # Rename the versioned file to an unversioned one
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

    # Get the latest tag from the pop-os repo
    def get_latest_tag(package: str) -> str:
        repo_name = PACKAGES[package]
        url = f"https://api.github.com/repos/pop-os/{repo_name}/tags"
        with urlopen(url) as response:
            data = json.load(response)
            res: str = data[0]["name"].strip()
            # Return the name with epoch- removed and with `-` replaced with `~`
            return res.split("epoch-", 1)[1].replace("-", "~")

    # Download the source rpm to the specified path
    def download_package(rpm_name: str, output_path: Path) -> str:
        # Get package download link
        url = f"https://copr.fedorainfracloud.org/api_3/package/?ownername=ryanabx&projectname=cosmic-epoch-tagged&packagename={rpm_name}&with_latest_succeeded_build=true"
        with requests.get(url) as response:
            data = response.json()
        source_package = data["builds"]["latest_succeeded"]["source_package"]["url"]
        logger.debug(f"[{rpm_name}]: Downloading {source_package} to {output_path}...")
        urlretrieve(source_package, output_path)
        return data["builds"]["latest_succeeded"]["source_package"]["version"]

    # Clones the relevant repo from https://src.fedoraproject.org
    def clone_fedpkg_repo(self):
        max_attempts = 5
        i = 0
        while not self.repo_dir.exists():
            if i >= max_attempts:
                raise Exception(f"{self.package}: Could not clone repo")
            try:
                # Clone fedpkg repo
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

    # True if a commit should happen
    def should_commit(self) -> bool:
        if self.force_build:
            return True
        # Run `git rev-parse HEAD` to get the latest commit hash
        old_commit_msg = subprocess.run(
            ["git", "-C", self.repo_dir, "log", "-1", "--pretty=%B"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout.strip()
        return old_commit_msg != self.commit_msg

    # True if we should build, false otherwise
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

    # Convert the branch string to a number
    def branch_to_number(branch: str) -> str:
        return branch[1:] if branch != "rawhide" else RAWHIDE_BRANCH[1:]

    # Returns true if something was built, false otherwise
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
                i = 0
                while i < 5:
                    try:
                        subprocess.run(
                            ["fedpkg", "push"],
                            cwd=self.repo_dir,
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        break
                    finally:
                        i += 1
        else:
            logger.info(
                f"[{self.package}, {branch}]: Commit skipped. Commit messages matched."
            )
        logger.debug(f"[{self.package}, {branch}]: Checking if should build...")
        if self.should_build(branch):
            try:
                if not self.dry_run:
                    if side_tag and branch in SIDE_TAG_BRANCHES:
                        subprocess.run(
                            ["fedpkg", "build", f"--target={side_tag}"],
                            cwd=self.repo_dir,
                            timeout=10,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        subprocess.run(
                            ["fedpkg", "build"],
                            cwd=self.repo_dir,
                            timeout=10,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
            except subprocess.TimeoutExpired:
                logger.info(f"[{self.package}, {branch}]: Building version {branch}\n")
                builds.append(f"{self.package} {branch}")
                return True
        else:
            logger.info(
                f"[{self.package}, {branch}]: Build skipped. A build was found with matching version {self.version}\n"
            )
            return False

    # Returns true if anything was built, false otherwise
    def build_with_side_tag(self, side_tag: str) -> bool:
        did_build_anything = False
        for br in FEDORA_BRANCHES:
            if br == "all":
                continue
            try:
                built_package = self.build_branch(br, side_tag)
                did_build_anything = did_build_anything or built_package
            except Exception as e:
                logger.error(f"[{self.package}, {br}]: Error({br}): {e}\n")
                errored.append(f"[{self.package} {br}]")
        return did_build_anything


def run_iteration(
    rpm_name: str,
    force_build: bool,
    side_tag: str,
    dry_run: bool,
    workdir: Path,
):
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
        # Clone repo
        pkg.clone_fedpkg_repo()

        time_before = datetime.datetime.now()
        # Do build
        did_build_anything = pkg.build_with_side_tag(side_tag)
        time_after = datetime.datetime.now()

        elapsed = time_after - time_before
        logger.info(f"[{pkg.package}]: === Done in {elapsed} seconds ===\n")

        if not did_build_anything:
            logger.info(f"[{pkg.package}]: {rpm_name}: Nothing was rebuilt.")
    except Exception as e:
        logger.error(f"[{rpm_name}]: Failed to run iteration: {e}")
        errored.append(f"{rpm_name} all")


parser = argparse.ArgumentParser(
    prog="cosmic_packaging_new_release",
    description="Program to manage new releases of COSMIC packages in upstream fedora repos",
)

parser.add_argument("--side-tag")
parser.add_argument("--dry-run", action="store_true")
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
parser.add_argument(
    "--workdir",
    type=Path,
    help="Working directory",
)

args = parser.parse_args()

# Handle --koji-status flag
if args.koji_status:
    if args.koji_package:
        check_koji_status_for_package(args.koji_package, PACKAGES, args.latest_version)
    else:
        check_koji_status(PACKAGES, args.latest_version)
    exit(0)

# Run multithreaded
import tempfile
from concurrent.futures import ThreadPoolExecutor


def build_package(package: str, force_build: bool, workdir: Path):
    working_directory = workdir.joinpath(package)
    try:
        logger.debug(f"[{package}]: Building package {package}")
        run_iteration(
            package, force_build, args.side_tag, args.dry_run, working_directory
        )
        logger.debug(f"[{package}]: Done building package {package}")
    finally:
        shutil.rmtree(working_directory)


package_force = []

workdir = args.workdir if args.workdir else Path(tempfile.mkdtemp())

if not args.rpm_name:  # All packages
    for pkg in PACKAGES.keys():
        package_force.append(args.force_package and pkg in args.force_package)
        if args.force_package and pkg in args.force_package:
            logger.warning("Forcing build of", pkg)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(
            executor.map(
                build_package,
                PACKAGES.keys(),
                package_force,
                [workdir] * len(PACKAGES.keys()),
            )
        )
else:  # One package
    build_package(
        args.rpm_name,
        args.force_package and args.rpm_name in args.force_package,
        workdir,
    )

builds.sort()
logger.info(f"Finished. Queued {len(builds)} builds: {builds}\nerrors: {errored}")
