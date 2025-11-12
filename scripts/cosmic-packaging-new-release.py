import subprocess
import argparse
import json
from urllib.request import urlopen, urlretrieve
from pathlib import Path

PACKAGES = [
    "cosmic-app-library",
    "cosmic-applets",
    "cosmic-bg",
    "cosmic-comp",
    "cosmic-edit",
    "cosmic-files",
    "cosmic-greeter",
    "cosmic-icon-theme",
    "cosmic-idle",
    "cosmic-initial-setup",
    "cosmic-launcher",
    "cosmic-notifications",
    "cosmic-osd",
    "cosmic-panel",
    "cosmic-player",
    "cosmic-randr",
    "cosmic-screenshot",
    "cosmic-session",
    "cosmic-settings",
    "cosmic-settings-daemon",
    "cosmic-store",
    "cosmic-term",
    "cosmic-wallpapers",
    "cosmic-workspaces",
    "xdg-desktop-portal-cosmic",
    "pop-launcher",
]

VERSIONS = [
    "rawhide",
    "f43",
    "f42",
    "f41",
]

RAWHIDE_BRANCH = "f44"

def branch_to_number(branch: str) -> str:
    return branch[1:] if branch != "rawhide" else RAWHIDE_BRANCH[1:]

WORKING_DIRECTORY: Path = Path.home().joinpath("workdir")
Path.mkdir(WORKING_DIRECTORY, exist_ok=True)


def get_latest_commit_name(repo_path="."):
    # Run `git rev-parse HEAD` to get the latest commit hash
    result = subprocess.run(
        ["git", "-C", repo_path, "log", "-1", "--pretty=%B"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def download_package(rpm_name: str, output_path: Path) -> str:
    # Get package download link
    print(f"Downloading package {rpm_name} to {output_path}...")
    url = f"https://copr.fedorainfracloud.org/api_3/package/?ownername=ryanabx&projectname=cosmic-epoch-tagged&packagename={rpm_name}&with_latest_succeeded_build=true"
    with urlopen(url) as response:
        data = json.load(response)
    source_package = data["builds"]["latest_succeeded"]["source_package"]["url"]
    urlretrieve(source_package, output_path)
    return data["builds"]["latest_succeeded"]["source_package"]["version"]

def should_build(rpm_name: str, branch: str, version: str) -> bool:
    check = subprocess.run(
        ["koji", "list-builds", f"--package={rpm_name}", "--state=COMPLETE", f"--pattern=*{version}.fc{branch_to_number(branch)}*", "--quiet"],
        capture_output=True,
        text=True
    )
    check2 = subprocess.run(
        ["koji", "list-builds", f"--package={rpm_name}", "--state=BUILDING", f"--pattern=*{version}.fc{branch_to_number(branch)}*", "--quiet"],
        capture_output=True,
        text=True
    )
    return check.stdout.strip() == "" and check2.stdout.strip() == "" and check.stderr.strip() == "" and check2.stderr.strip() == ""


def build_package(
    rpm_name: str, branch: str, version: str, side_tag: str | None = None
):
    print(f"Building {rpm_name} with branch {branch}")

    # Clone fedpkg repo
    rpm_dir = WORKING_DIRECTORY.joinpath(rpm_name)
    subprocess.run(
        ["fedpkg", "switch-branch", branch],
        cwd=rpm_dir,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    commit_msg = f"update to {version}"
    old_commit_msg = get_latest_commit_name(rpm_dir)
    if old_commit_msg != commit_msg:
        if not args.dry_run:
            subprocess.run(
                ["fedpkg", "import", "--skip-diffs", output_package],
                cwd=rpm_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["fedpkg", "commit", "-m", commit_msg],
                cwd=rpm_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["fedpkg", "push"],
                cwd=rpm_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        print("Commit skipped. Commit messages matched.")
    if should_build(rpm_name, branch, version):
        try:
            if not args.dry_run:
                if side_tag and branch == "rawhide":
                    subprocess.run(
                        ["fedpkg", "build", f"--target={side_tag}"],
                        cwd=rpm_dir,
                        timeout=10,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.run(
                        ["fedpkg", "build"],
                        cwd=rpm_dir,
                        timeout=10,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
        except subprocess.TimeoutExpired:
            print("Finished waiting for build.")
    else:
        print(f"Build skipped. A build was found with matching version {version}")
    return version


parser = argparse.ArgumentParser(
    prog="cosmic-packaging-bootstrap",
    description="Setup a nightly build of cosmic-packaging",
)

parser.add_argument("rpm_name", choices=PACKAGES)
parser.add_argument("--branch", choices=VERSIONS)
parser.add_argument("--side-tag")
parser.add_argument("--dry-run", action="store_true")

args = parser.parse_args()

print(f"RPM Name: {args.rpm_name}, Branch: {args.branch}, Side Tag: {args.side_tag}, Dry Run: {args.dry_run}")

output_package = WORKING_DIRECTORY.joinpath(f"{args.rpm_name}.src.rpm")
# Download src rpm, and return the version
version = download_package(args.rpm_name, output_package)
# Remove any build numbers at the end i.e. 1.0.0~beta.6"-1"
version = version.rsplit('-',maxsplit=1)[0]

subprocess.run(
    ["fedpkg", "clone", args.rpm_name],
    cwd=WORKING_DIRECTORY,
    check=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

if not args.branch:
    for br in VERSIONS:
        print(f"Version: {br}")
        if br == "all":
            continue
        try:
            build_package(args.rpm_name, br, version, args.side_tag)
        except Exception as e:
            print(f"Error when building {br}: {e}")
else:
    build_package(args.rpm_name, args.branch)
