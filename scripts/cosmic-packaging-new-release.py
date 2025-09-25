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
    "all"
]

WORKING_DIRECTORY: Path = Path.home().joinpath("workdir")
Path.mkdir(WORKING_DIRECTORY, exist_ok=True)

def download_package(rpm_name: str, output_path: Path) -> str:
    # Get package download link
    print(f"Downloading package {rpm_name} to {output_path}...")
    url = f"https://copr.fedorainfracloud.org/api_3/package/?ownername=ryanabx&projectname=cosmic-epoch-tagged&packagename={rpm_name}&with_latest_succeeded_build=true"
    with urlopen(url) as response:
        data = json.load(response)
    source_package = data["builds"]["latest_succeeded"]["source_package"]["url"]
    urlretrieve(source_package, output_path)
    print("Done!")
    return data["builds"]["latest_succeeded"]["source_package"]["version"]

def build_package(rpm_name: str, branch: str, version: str | None = None) -> str:
    print(f"Building {rpm_name} with branch {branch}")
    output_package = WORKING_DIRECTORY.joinpath(f"{rpm_name}.src.rpm")
    # Download src rpm
    if not version:
        version = download_package(rpm_name, output_package)
        subprocess.run(["fedpkg", "clone", rpm_name], cwd=WORKING_DIRECTORY, check=True)
    # Clone fedpkg repo
    rpm_dir = WORKING_DIRECTORY.joinpath(rpm_name)
    subprocess.run(["fedpkg", "switch-branch", branch], cwd=rpm_dir, check=True)
    subprocess.run(["fedpkg", "import", "--skip-diffs", output_package], cwd=rpm_dir, check=True)
    subprocess.run(["fedpkg", "commit", "-m", f"update to {version}"], cwd=rpm_dir, check=True)
    subprocess.run(["fedpkg", "push"], cwd=rpm_dir)
    try:
        subprocess.run(["fedpkg", "build"], cwd=rpm_dir, timeout=10)
    except subprocess.TimeoutExpired:
        print("Finished waiting for build.")
    return version

parser = argparse.ArgumentParser(
    prog="cosmic-packaging-bootstrap",
    description="Setup a nightly build of cosmic-packaging",
)

parser.add_argument("rpm_name", choices=PACKAGES)
parser.add_argument("branch", choices=VERSIONS)

args = parser.parse_args()

print(f"RPM Name: {args.rpm_name}, Branch: {args.branch}")

if args.branch == "all":
    downloaded_version = None
    for br in VERSIONS:
        print(f"Version: {br}")
        if br == "all":
            continue
        try:
            downloaded_version = build_package(args.rpm_name, br, downloaded_version)
        except Exception as e:
            print(f"Error when building {br}: {e}")
            break
else:
    build_package(args.rpm_name, args.branch)
