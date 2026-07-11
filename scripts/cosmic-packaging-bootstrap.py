import argparse
import subprocess
import pathlib
import os
import shutil
import datetime
from urllib.request import urlopen
from urllib.parse import urlparse
import json

import sys

import tempfile


class ProjectInfo:
    POP_OS_GIT = "https://github.com/pop-os/"
    FEDORA_GIT = "https://src.fedoraproject.org/rpms/"

    COSMIC_PACKAGING_GIT = "https://forge.fedoraproject.org/cosmic/cosmic-packaging.git"

    def __init__(
        self,
        rpm_name: str,
        crate_name: str = "",
        vendor: bool = True,
        apply_patches_early: bool = False,
        zip_self: bool = False,
        staging: bool = False,
        upstream_tag: str = "",
        release_override: str | None = None,
        latest_tag: str | None = None,
    ):
        self.rpm_name = rpm_name
        self.crate_name = crate_name if crate_name else rpm_name
        self.vendor = vendor
        self.apply_patches_early = apply_patches_early
        self.zip_self = zip_self
        self.staging = staging
        self.upstream_tag = upstream_tag
        self.upstream_git = ProjectInfo.POP_OS_GIT + self.crate_name + ".git"
        self.fedora_git = ProjectInfo.FEDORA_GIT + self.rpm_name + ".git"
        self.release_override = release_override
        self.ignore_patches: list[str] = []
        self.latest_tag = latest_tag

    def clone_upstream_git(
        self,
        base_dir: pathlib.Path,
    ):
        print("clone_upstream_git")
        subprocess.run(
            [
                "git",
                "clone",
                "--recurse-submodules",
                self.upstream_git,
            ],
            cwd=base_dir,
            check=True,
        )

    def clone_fedora_git(
        self,
        base_dir: pathlib.Path,
    ):
        print("clone_fedora_git")
        if self.staging:
            # Clone cosmic-packaging git and copy the proper subdirectory to the base dir
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--recurse-submodules",
                    ProjectInfo.COSMIC_PACKAGING_GIT,
                ],
                cwd=base_dir,
                check=True,
            )
            subprocess.run(
                [
                    "mv",
                    base_dir.joinpath("cosmic-packaging")
                    .joinpath("staging")
                    .joinpath(self.rpm_name),
                    base_dir.joinpath(self.rpm_name),
                ],
                cwd=base_dir,
                check=True,
            )
            subprocess.run(
                ["rm", "-r", base_dir.joinpath("cosmic-packaging")],
                cwd=base_dir,
                check=True,
            )
        else:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--recurse-submodules",
                    self.fedora_git,
                ],
                cwd=base_dir,
                check=True,
            )


class DirectoryInfo:
    PATCH_DIRECTORY = "./patches"
    RPM_DIRECTORY = "./fedora"

    def __init__(
        self,
        project_info: ProjectInfo,
        input_dir: pathlib.Path,
        output_dir: pathlib.Path,
        fedora_dir: pathlib.Path | None,
        upstream_project_dir: pathlib.Path | None,
    ):
        self.input_dir = input_dir.absolute()
        self.output_dir = output_dir.absolute()
        # Create output directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
        # Standard directories
        self.patch_directory = (
            input_dir.joinpath(DirectoryInfo.PATCH_DIRECTORY)
            .joinpath(project_info.rpm_name)
            .absolute()
        )
        if not self.patch_directory.exists():
            self.patch_directory.mkdir(parents=True, exist_ok=True)
        # Cloned git artifact directories
        self.upstream_project_directory = (
            output_dir.joinpath(project_info.crate_name).absolute()
            if not upstream_project_dir
            else upstream_project_dir.absolute()
        )
        self.fedora_project_directory = (
            (
                output_dir.joinpath(DirectoryInfo.RPM_DIRECTORY)
                .joinpath(project_info.rpm_name)
                .absolute()
            )
            if not fedora_dir
            else fedora_dir.absolute()
        )
        if not self.fedora_project_directory.parent.exists():
            self.fedora_project_directory.parent.mkdir(parents=True, exist_ok=True)

        # Clone the project git repos
        if not upstream_project_dir:
            project_info.clone_upstream_git(
                base_dir=self.upstream_project_directory.parent
            )
        if not fedora_dir:
            project_info.clone_fedora_git(base_dir=self.fedora_project_directory.parent)

        print(
            "input_dir:",
            self.input_dir,
            "output_dir:",
            self.output_dir,
            "patch_directory:",
            self.patch_directory,
            "upstream_project_directory:",
            self.upstream_project_directory,
            "fedora_project_directory:",
            self.fedora_project_directory,
        )


class TagInfo:
    # Get the latest tag from the pop-os repo
    @staticmethod
    def get_latest_tag(package: str) -> str:
        repo_name = package
        url = f"https://api.github.com/repos/pop-os/{repo_name}/tags"
        with urlopen(url) as response:
            data = json.load(response)
            res: str = data[0]["name"].strip()
            # Return the name with epoch- removed and with `-` replaced with `~`
            return res.split("epoch-", 1)[1].replace("-", "~")

    def __init__(
        self, directory_info: DirectoryInfo, tag: str | None, minver_tag: str | None
    ):
        # Nightly specified if tag not specified
        self.nightly = tag is None
        # If nightly
        commit = "" if self.nightly else str("epoch-" + tag).replace("~", "-")  # type: ignore

        if self.nightly:
            print("Nightly, so tag is accessed through rev-parse")
            # When we don't get a specific tag (i.e. nightly), our 'tag' becomes the shortcommit
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=directory_info.upstream_project_directory,
                check=True,
            ).stdout.strip()
            print(f"Commit: {commit}")
            tag = commit[:7]

        self.tag = tag
        self.tag_no_tilde = self.tag.replace("~", "-")  # type: ignore
        self.minver_tag = minver_tag

        print("Git reset")
        subprocess.run(
            ["git", "reset", "--hard", commit],
            cwd=directory_info.upstream_project_directory,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", commit],
            cwd=directory_info.upstream_project_directory,
            check=True,
        )

        print("Git rev-parse")
        self.commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=directory_info.upstream_project_directory,
            check=True,
        ).stdout.strip()

        self.commit_date = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d"],
            capture_output=True,
            text=True,
            cwd=directory_info.upstream_project_directory,
            check=True,
        ).stdout.strip()
        self.commit_date_string = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=iso"],
            capture_output=True,
            text=True,
            cwd=directory_info.upstream_project_directory,
            check=True,
        ).stdout.strip()

        print(
            "tag:",
            self.tag,
            "tag_no_tilde:",
            self.tag_no_tilde,
            "commit:",
            self.commit,
            "commit_date:",
            self.commit_date,
            "commit_date_string:",
            self.commit_date_string,
        )


class ProjectOperations:
    def __init__(
        self,
        project_info: ProjectInfo,
        directory_info: DirectoryInfo,
        tag_info: TagInfo,
    ):
        self.project_info = project_info
        self.directory_info = directory_info
        self.tag_info = tag_info

    # Patches crates that are known to have bad executable bits
    def patch_vendored_crates(self):
        print("patch_vendored_crates")

        # remove executable bit of some .rs files
        subprocess.run(
            [
                "find",
                "./vendor",
                "-name",
                "*.rs",
                "-type",
                "f",
                "-exec",
                "chmod",
                "-x",
                "{}",
                "+",
            ],
            cwd=self.directory_info.upstream_project_directory,
            check=False,
        )

    @staticmethod
    def _apply_patch(patch: pathlib.Path | str, repo: pathlib.Path):
        print("Applying patch:", patch)
        ot = subprocess.run(
            [
                "git",
                "apply",
                # "am",
                str(patch),
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if ot.returncode != 0:
            print("Patch failed!\n", ot.stdout.strip(), ot.stderr.strip())
            sys.exit(-1)

    # Apply patches from the fedora repo to the upstream vendoring repository
    def _apply_patches_to_upstream(self, repo: pathlib.Path) -> None:
        print("Applying patches to upstream repository from fedora repo")
        fedora_patch_dir = self.directory_info.fedora_project_directory
        if not fedora_patch_dir.exists():
            print(f"No fedora project directory found: {fedora_patch_dir}")
            return

        patch_files = sorted(fedora_patch_dir.glob("*.patch"))
        failed_patches: list[str] = []
        for patch_file in patch_files:
            if patch_file.name in self.project_info.ignore_patches:
                print(f"Ignoring {patch_file.name} due to override...")
                continue
            print(f"Applying patch: {patch_file.name}")
            ot = subprocess.run(
                [
                    "git",
                    "apply",
                    str(patch_file),
                ],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            if ot.returncode != 0:
                print(f"Patch failed: {patch_file.name}")
                print(f"  stdout: {ot.stdout.strip()}")
                print(f"  stderr: {ot.stderr.strip()}")
                failed_patches.append(patch_file.name)

        if failed_patches:
            print(
                f"\nERROR: {len(failed_patches)} patch(es) failed to apply to the upstream repository:"
            )
            for failed in failed_patches:
                print(f"  - {failed}")
            print("\nPlease ensure all patches are applicable to the upstream repository.")
            sys.exit(-1)
        print(f"Successfully applied {len(patch_files)} patch(es)")

    # This function prepares the vendored artifacts for the package
    def vendor(self):
        print("vendor")
        # Clone upstream to a temporary directory for patching and vendoring
        vendoring_temp_dir = tempfile.mkdtemp()
        vendoring_temp_path = pathlib.Path(vendoring_temp_dir)
        try:
            print(f"Cloning upstream to temp directory for vendoring: {vendoring_temp_dir}")
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--recurse-submodules",
                    self.project_info.upstream_git,
                    str(vendoring_temp_path / "repo"),
                ],
                cwd=vendoring_temp_path,
                check=True,
            )
            vendoring_repo = vendoring_temp_path / "repo"

            # Checkout the correct commit
            print(f"Checking out commit: {self.tag_info.commit}")
            subprocess.run(
                ["git", "reset", "--hard", self.tag_info.commit],
                cwd=vendoring_repo,
                check=True,
            )

            # Apply patches from the patches directory to the vendoring repo
            self._apply_patches_to_upstream(vendoring_repo)

            # Run cargo vendor
            cargo_vendor_output = subprocess.run(
                [
                    "cargo",
                    "vendor",
                    "--locked",
                ],
                capture_output=True,
                text=True,
                cwd=vendoring_repo,
                check=True,
            )
            print("Cargo vendor output\n", cargo_vendor_output.stderr.strip(), "\n")

            # Write the vendor config to the output directory
            with open(
                self.directory_info.output_dir.joinpath(
                    "vendor-config-" + self.tag_info.tag_no_tilde + ".toml"
                ),
                "w",
            ) as f:
                f.write(cargo_vendor_output.stdout.strip())

            # Patch crates that need patching
            self.patch_vendored_crates()

            # Zip up the vendored crates
            subprocess.run(
                [
                    "tar",
                    "-pczf",
                    self.directory_info.output_dir.joinpath(
                        "vendor-" + self.tag_info.tag_no_tilde + ".tar.gz"
                    ),
                    "vendor",
                ],
                cwd=vendoring_repo,
                check=True,
            )
        finally:
            # Always clean up the temporary vendoring directory
            print(f"Cleaning up vendoring temp directory: {vendoring_temp_dir}")
            shutil.rmtree(vendoring_temp_dir)

    # This function copies files from the fedora upstream rpm source to the output directory
    def copy_fedora_files_to_output(self):
        print("copy_fedora_files_to_output")
        for root, _dirs, files in os.walk(self.directory_info.fedora_project_directory):
            # Skip .git
            if pathlib.Path(root).is_relative_to(
                self.directory_info.fedora_project_directory.joinpath(".git")
            ):
                print(f"Found .git directory. {root} Continuing...")
                continue
            relative_path = os.path.relpath(
                root, self.directory_info.fedora_project_directory
            )

            dest_path = os.path.join(self.directory_info.output_dir, relative_path)

            os.makedirs(dest_path, exist_ok=True)  # Ensure destination subdir exists

            for file in files:
                # Skip vendor-config
                if file.count("vendor-config") > 0:
                    continue
                try:
                    shutil.copy2(
                        os.path.join(root, file), os.path.join(dest_path, file)
                    )  # Preserve metadata
                except Exception as e:
                    print(f"Could not copy file {os.path.join(root, file)}: ", e)
        # Don't copy sources (since we have the sources in our directory now presumably)
        self.directory_info.output_dir.joinpath("sources").unlink(missing_ok=True)
        self.directory_info.output_dir.joinpath(
            self.project_info.rpm_name + ".spec"
        ).unlink(missing_ok=True)

    # Prepare the rpm spec repo by applying patches and modifying the spec file
    def prepare_spec_repo(self):
        print("prepare_spec_repo")
        print(f"Patches to ignore: {self.project_info.ignore_patches}")
        spec_path = self.directory_info.fedora_project_directory.joinpath(
            f"{self.project_info.rpm_name}.spec"
        )
        output_path = self.directory_info.output_dir.joinpath(
            f"{self.project_info.rpm_name}.spec"
        )
        # Apply downstream -nightly patches
        for root, _dirs, files in os.walk(self.directory_info.patch_directory):
            for file in files:
                if file.strip() in self.project_info.ignore_patches:
                    print(f"Ignoring {file} due to override...")
                    continue
                ProjectOperations._apply_patch(
                    os.path.join(root, file),
                    self.directory_info.fedora_project_directory,
                )

        # Copy the files to the output
        self.copy_fedora_files_to_output()

        # Make spec file modifications
        with open(spec_path, "r") as f:
            spec_res = SpecFile(self.project_info, self.tag_info, f.read())
            # If patches exist, and we preapply patches, do this now
            if self.project_info.apply_patches_early:
                patches = spec_res.get_listed_patches()
                for patch in patches:
                    if ProjectOperations._is_url(patch):
                        ProjectOperations._apply_patch_from_url(
                            patch, self.directory_info.upstream_project_directory
                        )
                    else:
                        ProjectOperations._apply_patch_from_file(
                            self.directory_info.fedora_project_directory.joinpath(
                                patch
                            ),
                            self.directory_info.upstream_project_directory,
                        )
            with open(output_path, "w") as f2:
                f2.write(spec_res.spec_out)

    @staticmethod
    def _is_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"}

    @staticmethod
    def _download_text(url: str, encoding: str = "utf-8") -> str:
        with urlopen(url) as response:
            return response.read().decode(encoding)

    @staticmethod
    def _apply_patch_from_url(url: str, repo: pathlib.Path) -> None:
        print("Pre-Applying patch from url:", url)
        response = ProjectOperations._download_text(url)
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".patch"
        ) as tmp:
            tmp.writelines(response)
            tmp_path = tmp.name

        try:
            ProjectOperations._apply_patch(tmp_path, repo)
        finally:
            os.unlink(tmp_path)

    @staticmethod
    def _apply_patch_from_file(path: pathlib.Path, repo: pathlib.Path) -> None:
        print("Pre-Applying patch from file:", path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Patch file not found: {path}")

        ProjectOperations._apply_patch(path, repo)

    # Performs the remainder of setup needed to build the rpm
    def setup(self):
        print("setup")
        # Prepare the Fedora spec side
        self.prepare_spec_repo()
        # If we are building a project that needs vendoring, do that now
        if self.project_info.vendor:
            self.vendor()
        # If we want to zip our output as an artifact, do so now
        if self.project_info.zip_self:
            # tar -pczf cosmic-wallpapers-%{version_no_tilde}.tar.gz cosmic-wallpapers
            zip_result = subprocess.run(
                [
                    "tar",
                    "-pczf",
                    f"{self.project_info.crate_name}-{self.tag_info.tag_no_tilde}.tar.gz",
                    self.project_info.crate_name,
                ],
                cwd=self.directory_info.output_dir,
                text=True,
                capture_output=True,
                check=True,
            )
            print(zip_result.stdout.strip())


# Spec file processing class
class SpecFile:
    def __init__(self, project_info: ProjectInfo, tag_info: TagInfo, spec_in: str):
        if tag_info.nightly:
            self.spec_out = self.process_nightly(project_info, tag_info, spec_in)
        else:
            self.spec_out = self.process_tagged(project_info, tag_info, spec_in)

    def process_nightly(
        self, project_info: ProjectInfo, tag_info: TagInfo, spec_in: str
    ) -> str:
        build_date = datetime.datetime.now().strftime("%Y%m%d%H%M")
        out_str = ""
        skip = False
        for in_line in spec_in.splitlines():
            out_line = in_line
            if (
                in_line.startswith("%global commit ")
                or in_line.startswith(
                    "# While our version corresponds to an upstream tag"
                )
            ) and not skip:
                out_str += f"# cosmic-packaging: Nightly build processed from tagged version at {project_info.fedora_git}\n"
                out_str += f"%global commit {tag_info.commit}\n"
                out_str += "%global shortcommit %{sub %{commit} 1 7}\n"
                out_str += f"%global commitdatestring {tag_info.commit_date_string}\n"
                out_str += f"%global commitdate {tag_info.commit_date}\n"
                out_str += f"%global builddate {build_date}\n"
                out_str += f"%global cosmic_minver {tag_info.minver_tag}\n\n"
                skip = True
            elif in_line.startswith("Name: "):
                skip = False
            elif in_line.startswith("Version: "):
                if project_info.upstream_tag:
                    print(
                        f"Version: {project_info.upstream_tag}^git{tag_info.commit_date}.{tag_info.commit[:7]}"
                    )
                    out_line = f"Version: {project_info.upstream_tag}^git%{{commitdate}}.%{{shortcommit}}"
                else:
                    print(
                        f"Version: {tag_info.minver_tag}^git{tag_info.commit_date}.{tag_info.commit[:7]}"
                    )
                    out_line = f"Version: {tag_info.minver_tag}^git%{{commitdate}}.%{{shortcommit}}"
            elif in_line.startswith("Source0: "):
                out_line = out_line.replace("epoch-%{version_no_tilde}", "%{commit}")
            elif in_line.startswith("Release: ") and project_info.release_override:
                out_line = f"Release: {project_info.release_override}"
            elif in_line.startswith("%autosetup "):
                out_line = out_line.replace("epoch-%{version_no_tilde}", "%{commit}")

            out_line = out_line.replace("%{version_no_tilde}", "%{shortcommit}")
            if not skip:
                out_str += out_line.rstrip() + "\n"
        return out_str

    # This function processes an input spec file as a string, and outputs the result to another string
    def process_tagged(
        self, project_info: ProjectInfo, tag_info: TagInfo, spec_in: str
    ) -> str:
        out_str = ""
        skip = False
        for in_line in spec_in.splitlines():
            out_line = in_line
            if in_line.startswith("# Generated using the scripts"):
                out_line = "# Generated using the scripts at # Generated using the scripts at https://forge.fedoraproject.org/cosmic/cosmic-packaging/src/branch/main/scripts"
            elif (
                in_line.startswith("%global commit ")
                or in_line.startswith(
                    "# While our version corresponds to an upstream tag"
                )
            ) and not skip:
                out_str += "# While our version corresponds to an upstream tag, we still need to define\n"
                out_str += "# these macros in order to set the VERGEN_GIT_SHA and VERGEN_GIT_COMMIT_DATE\n"
                out_str += (
                    "# environment variables in multiple sections of the spec file.\n"
                )
                out_str += f"%global commit {tag_info.commit}\n"
                out_str += f"%global commitdatestring {tag_info.commit_date_string}\n"
                out_str += f"%global cosmic_minver {tag_info.tag}\n\n"
                skip = True
            elif in_line.startswith("Name: "):
                skip = False
            elif in_line.startswith("Version: "):
                out_line = f"Version: {tag_info.tag}"
            elif in_line.startswith("Source0: "):
                out_line = out_line.replace("%{commit}", "epoch-%{version_no_tilde}")
            elif in_line.startswith("%autosetup "):
                out_line = out_line.replace("%{commit}", "epoch-%{version_no_tilde}")

            out_line = out_line.replace("%{shortcommit}", "%{version_no_tilde}")
            if not skip:
                out_str += out_line.rstrip() + "\n"
        return out_str

    def get_listed_patches(self) -> list[str]:
        patch_list: list[str] = []
        for line in self.spec_out.splitlines():
            if not line.startswith("Patch:"):
                continue

            patch_ref = line[len("Patch:") :].strip()
            if not patch_ref:
                continue

            patch_list.append(patch_ref)
        return patch_list


# Define every COSMIC package
PACKAGE_INFO: dict[str, ProjectInfo] = {
    "cosmic-app-library": ProjectInfo(
        rpm_name="cosmic-app-library", crate_name="cosmic-applibrary"
    ),
    "cosmic-applets": ProjectInfo(rpm_name="cosmic-applets"),
    "cosmic-bg": ProjectInfo(rpm_name="cosmic-bg"),
    "cosmic-comp": ProjectInfo(rpm_name="cosmic-comp"),
    "cosmic-edit": ProjectInfo(rpm_name="cosmic-edit"),
    "cosmic-files": ProjectInfo(rpm_name="cosmic-files"),
    "cosmic-greeter": ProjectInfo(rpm_name="cosmic-greeter", release_override="2"),
    "cosmic-icon-theme": ProjectInfo(
        rpm_name="cosmic-icon-theme", crate_name="cosmic-icons", vendor=False
    ),
    "cosmic-idle": ProjectInfo(rpm_name="cosmic-idle"),
    "cosmic-initial-setup": ProjectInfo(rpm_name="cosmic-initial-setup", zip_self=True),
    "cosmic-launcher": ProjectInfo(rpm_name="cosmic-launcher"),
    "cosmic-monitor": ProjectInfo(rpm_name="cosmic-monitor", staging=True),
    "cosmic-notifications": ProjectInfo(rpm_name="cosmic-notifications"),
    "cosmic-osd": ProjectInfo(rpm_name="cosmic-osd"),
    "cosmic-panel": ProjectInfo(rpm_name="cosmic-panel"),
    "cosmic-player": ProjectInfo(rpm_name="cosmic-player"),
    "cosmic-randr": ProjectInfo(rpm_name="cosmic-randr"),
    "cosmic-screenshot": ProjectInfo(rpm_name="cosmic-screenshot"),
    "cosmic-session": ProjectInfo(rpm_name="cosmic-session"),
    "cosmic-settings": ProjectInfo(rpm_name="cosmic-settings"),
    "cosmic-settings-daemon": ProjectInfo(rpm_name="cosmic-settings-daemon"),
    "cosmic-store": ProjectInfo(rpm_name="cosmic-store"),
    "cosmic-term": ProjectInfo(rpm_name="cosmic-term"),
    "cosmic-wallpapers": ProjectInfo(
        rpm_name="cosmic-wallpapers", vendor=False, zip_self=True
    ),
    "cosmic-workspaces": ProjectInfo(
        rpm_name="cosmic-workspaces", crate_name="cosmic-workspaces-epoch"
    ),
    "xdg-desktop-portal-cosmic": ProjectInfo(rpm_name="xdg-desktop-portal-cosmic"),
    "pop-launcher": ProjectInfo(
        rpm_name="pop-launcher", crate_name="launcher", upstream_tag="1.2.7"
    ),
}

# if [ "$NIGHTLY" -eq 1 ]; then
#     echo "NIGHTLY=1"
#     sed -i "/^Version: / s/.*/Version:        $VERSION^git%{commitdate}.%{shortcommit}/" $NAME.spec
#     sed -i "/^%global commitdate / s/.*/%global commitdate $COMMITDATE/" $NAME.spec
#     sed -i "/^%global commit / s/.*/%global commit $COMMIT/" $NAME.spec
# else
#     sed -i "/^Version: / s/.*/Version:        $VERSION/" $NAME.spec
#     # Replace shortcommit with version_no_tilde and delete shortcommit def. version_no_tilde is predefined by rpm macros
#     sed -i "/^%global shortcommit /d" $NAME.spec
#     # Replace commit in Source0 with epoch-%version_no_tilde
#     sed -i "/^Source0/ s/%{commit}/epoch-%{version_no_tilde}/g" $NAME.spec
#     sed -i "/^%autosetup/ s/%{commit}/epoch-%{version_no_tilde}/g" $NAME.spec
#     sed -i "s/%{shortcommit}/%{version_no_tilde}/g" $NAME.spec
#     # Delete commitdate, we don't need it here
#     sed -i "/^%global commitdate /d" $NAME.spec
#     # We still need commit, add comments explaining why
#     sed -i "/^%global commit / s/.*/\# While our version corresponds to an upstream tag, we still need to define\n\# these macros in order to set the VERGEN_GIT_SHA and VERGEN_GIT_COMMIT_DATE\n\# environment variables in multiple sections of the spec file.\n%global commit $COMMIT/" $NAME.spec
# fi

#################
# CLI ARGUMENTS #
#################

parser = argparse.ArgumentParser(
    prog="cosmic-packaging-bootstrap",
    description="Setup a nightly build of cosmic-packaging",
)

parser.add_argument("rpm_name", choices=list(PACKAGE_INFO.keys()))
parser.add_argument(
    "--tag",
    help="Tag to use. Defaults to latest commit (Nightly). Specify --tag latest to get latest tag",
)
parser.add_argument("--input", help="Input directory (cosmic-packaging repo) to use.")
parser.add_argument("--output", help="Output directory to use.")
parser.add_argument(
    "--upstream-dir",
    help="Provide a pre-cloned cosmic-<NAME> source at this specified directory.",
)
parser.add_argument(
    "--fedora-dir",
    help="Provide a pre-cloned upstream source at this specified directory.",
)
parser.add_argument(
    "--pre-apply-spec-patches",
    action="store_true",
    help="Force patches to be pre-applied even if the project doesn't automatically do so.",
)
parser.add_argument(
    "--zip-self",
    action="store_true",
    help="Force project to be zipped even if it's not done automatically.",
)
parser.add_argument(
    "--ignore-patch",
    action="append",
    help="Ignore applying a patch temporarily (useful for tagged version releases)",
)

###############
# RUN PROGRAM #
###############

args = parser.parse_args()
# Identify project
project_info = PACKAGE_INFO[args.rpm_name]

# Overrides
if args.pre_apply_spec_patches:
    project_info.apply_patches_early = args.pre_apply_spec_patches

if args.zip_self:
    project_info.zip_self = args.zip_self

if args.ignore_patch:
    project_info.ignore_patches = args.ignore_patch


# Get input directory and output directory
# Depends on project_info to get the subdirectory names
# This instantiation will clone the projects into their proper directories as well
directory_info = DirectoryInfo(
    project_info=project_info,
    input_dir=pathlib.Path(args.input) if args.input else pathlib.Path.cwd(),
    output_dir=pathlib.Path(args.output) if args.output else pathlib.Path.cwd(),
    upstream_project_dir=pathlib.Path(args.upstream_dir) if args.upstream_dir else None,
    fedora_dir=pathlib.Path(args.fedora_dir) if args.fedora_dir else None,
)
# Normalize tag argument from the command line
tag = args.tag

if project_info.latest_tag is None:
    latest_tag = TagInfo.get_latest_tag(project_info.crate_name)
else:
    latest_tag = project_info.latest_tag

if args.tag == "latest":
    tag = latest_tag
elif tag == "nightly":
    tag = None
# Get information about tags, using the cloned project
# This also gets the git project into the correct revision by checking out the proper rev
tag_info = TagInfo(directory_info=directory_info, tag=tag, minver_tag=latest_tag)

project_operations = ProjectOperations(project_info, directory_info, tag_info)
project_operations.setup()

# We are now set up with all the variables we need to prepare the output for rpm building
# Finally, clean up by removing the cloned repos
if not args.upstream_dir:
    shutil.rmtree(directory_info.upstream_project_directory)
if not args.fedora_dir:
    shutil.rmtree(directory_info.fedora_project_directory.parent)


print("ls -a")
ls_result = subprocess.run(
    [
        "ls",
        "-a",
    ],
    cwd=directory_info.output_dir,
    text=True,
    capture_output=True,
    check=True,
)
print(ls_result.stdout.strip())
