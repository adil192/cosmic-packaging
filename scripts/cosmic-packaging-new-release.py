import subprocess
import argparse
import json
from urllib.request import urlopen, urlretrieve
from pathlib import Path
import datetime

# Possible packages to build
PACKAGES: dict[str, str] = {
    "cosmic-app-library": "cosmic-applibrary",
    "cosmic-applets": "cosmic-applets",
    "cosmic-bg": "cosmic-bg",
    "cosmic-comp": "cosmic-comp",
    "cosmic-edit": "cosmic-edit",
    "cosmic-files": "cosmic-files",
    "cosmic-greeter": "cosmic-greeter",
    "cosmic-icon-theme": "cosmic-icons",
    "cosmic-idle": "cosmic-idle",
    "cosmic-initial-setup": "cosmic-initial-setup",
    "cosmic-launcher": "cosmic-launcher",
    "cosmic-notifications": "cosmic-notifications",
    "cosmic-osd": "cosmic-osd",
    "cosmic-panel": "cosmic-panel",
    "cosmic-player": "cosmic-player",
    "cosmic-randr": "cosmic-randr",
    "cosmic-screenshot": "cosmic-screenshot",
    "cosmic-session": "cosmic-session",
    "cosmic-settings": "cosmic-settings",
    "cosmic-settings-daemon": "cosmic-settings-daemon",
    "cosmic-store": "cosmic-store",
    "cosmic-term": "cosmic-term",
    "cosmic-wallpapers": "cosmic-wallpapers",
    "cosmic-workspaces": "cosmic-workspaces-epoch",
    "xdg-desktop-portal-cosmic": "xdg-desktop-portal-cosmic",
    "pop-launcher": "launcher",
}

# Possible versions
VERSIONS = ["rawhide", "f43", "f42", "f41"]
RAWHIDE_BRANCH = "f44"

class PackageBuilder:
    def __init__(self, package: str, dry_run: bool, working_directory: Path):
        self.package = package
        self.dry_run = dry_run
        self.working_directory = working_directory
        self.tag = PackageBuilder.get_latest_tag(self.package)
        print(f"Latest tag for package: {self.tag}")
        self.src_rpm = self.working_directory.joinpath(f"{self.package}.src.rpm")
        # Download src rpm, and return the version
        # Remove any build numbers at the end i.e. 1.0.0~beta.8"-1"
        self.version = PackageBuilder.download_package(self.package, self.src_rpm).rsplit("-", maxsplit=1)[0]
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
        # print(f"Downloading package {rpm_name} to {output_path}...")
        url = f"https://copr.fedorainfracloud.org/api_3/package/?ownername=ryanabx&projectname=cosmic-epoch-tagged&packagename={rpm_name}&with_latest_succeeded_build=true"
        with urlopen(url) as response:
            data = json.load(response)
        source_package = data["builds"]["latest_succeeded"]["source_package"]["url"]
        print(f"Downloading {source_package} to {output_path}...")
        urlretrieve(source_package, output_path)
        return data["builds"]["latest_succeeded"]["source_package"]["version"]
    
    # Clones the relevant repo from https://src.fedoraproject.org
    def clone_fedpkg_repo(self):
        # Clone fedpkg repo
        subprocess.run(
            ["fedpkg", "clone", self.package],
            cwd=self.working_directory,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # True if a commit should happen
    def should_commit(self) -> bool:
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
        check = subprocess.run(
            [
                "koji",
                "list-builds",
                f"--package={self.package}",
                "--state=COMPLETE",
                f"--pattern=*{self.version}*.fc{PackageBuilder.branch_to_number(branch)}*",
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
                f"--pattern=*{self.version}*.fc{PackageBuilder.branch_to_number(branch)}*",
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        currently_finished = check.stdout.strip()
        currently_building = check2.stdout.strip()
        if currently_finished != "":
            print(f"{branch}: Found finished builds: {currently_finished.split('\n')}\n")
        if currently_building != "":
            print(
                f"{branch}: Found currently building builds: {currently_building.split('\n')}\n"
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
        subprocess.run(
            ["fedpkg", "switch-branch", branch],
            cwd=self.repo_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
                subprocess.run(
                    ["fedpkg", "push"],
                    cwd=self.repo_dir,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        else:
            print("Commit skipped. Commit messages matched.")

        if self.should_build(branch):
            try:
                if not self.dry_run:
                    if side_tag and branch == "rawhide":
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
                print(f"Building version {branch}\n")
                return True
        else:
            print(f"Build skipped. A build was found with matching version {self.version}\n")
            return False
    
    # Returns true if anything was built, false otherwise
    def build_with_side_tag(self, side_tag: str) -> bool:
        did_build_anything = False
        for br in VERSIONS:
            print(f"=== Branch: {br} ===\n")
            if br == "all":
                continue
            try:
                built_package = self.build_branch(br, side_tag)
                did_build_anything = did_build_anything or built_package
            except Exception as e:
                print(f"Error({br}): {e}\n")
        return did_build_anything


def run_iteration(rpm_name: str, side_tag: str, dry_run: bool):
    working_directory = Path.home().joinpath("workdir").joinpath(rpm_name)
    Path.mkdir(working_directory, exist_ok=True, parents=True)
    pkg = PackageBuilder(rpm_name, dry_run, working_directory)

    if pkg.tag == "":
        print(f"Could not get latest tag from https://github.com/pop-os/{PACKAGES[rpm_name]}")
        return

    if pkg.version != pkg.tag:
        print("Latest version does not equal the latest tag. Aborting")
        return
    # Clone repo
    pkg.clone_fedpkg_repo()

    time_before = datetime.datetime.now()
    # Do build
    did_build_anything = pkg.build_with_side_tag(side_tag)
    time_after = datetime.datetime.now()

    elapsed = time_after - time_before
    print(f"=== Done in {elapsed} seconds ===\n")

    if not did_build_anything:
        print(f"{rpm_name}: Nothing was rebuilt.")

parser = argparse.ArgumentParser(
    prog="cosmic_packaging_new_release",
    description="Program to manage new releases of COSMIC packages in upstream fedora repos",
)

parser.add_argument("--side-tag")
parser.add_argument("--dry-run", action="store_true")

args = parser.parse_args()

for package in PACKAGES.keys():
    print(f"Building package {package}")
    run_iteration(package, args.side_tag, args.dry_run)