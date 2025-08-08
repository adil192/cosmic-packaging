import argparse
import subprocess
import pathlib
import os
import shutil
import datetime


class ProjectInfo:
    POP_OS_GIT = "https://github.com/pop-os/"
    FEDORA_GIT = "https://src.fedoraproject.org/rpms/"

    COSMIC_PACKAGING_GIT = "https://pagure.io/fedora-cosmic/cosmic-packaging.git"

    def __init__(
        self,
        rpm_name: str,
        crate_name: str = "",
        vendor: bool = True,
        apply_patches: bool = False,
        zip_self: bool = False,
        staging: bool = False,
        upstream_tag: str = "",
    ):
        self.rpm_name = rpm_name
        self.crate_name = crate_name if crate_name else rpm_name
        self.vendor = vendor
        self.apply_patches = apply_patches
        self.zip_self = zip_self
        self.staging = staging
        self.upstream_tag = upstream_tag
        self.upstream_git = ProjectInfo.POP_OS_GIT + self.crate_name + ".git"
        self.fedora_git = ProjectInfo.FEDORA_GIT + self.rpm_name + ".git"

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
            ),
            subprocess.run(
                [
                    "mv",
                    base_dir.joinpath("cosmic-packaging")
                    .joinpath("staging")
                    .joinpath(self.rpm_name),
                    base_dir.joinpath(self.rpm_name),
                ],
                cwd=base_dir,
            )
            subprocess.run(
                ["rm", "-r", base_dir.joinpath("cosmic-packaging")], cwd=base_dir
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
            )


class DirectoryInfo:
    PATCH_DIRECTORY = "./patches"
    RPM_DIRECTORY = "./fedora"

    def __init__(
        self,
        project_info: ProjectInfo,
        input_dir: pathlib.Path,
        output_dir: pathlib.Path,
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
        self.upstream_project_directory = output_dir.joinpath(
            project_info.crate_name
        ).absolute()
        self.fedora_project_directory = (
            output_dir.joinpath(DirectoryInfo.RPM_DIRECTORY)
            .joinpath(project_info.rpm_name)
            .absolute()
        )
        if not self.fedora_project_directory.parent.exists():
            self.fedora_project_directory.parent.mkdir(parents=True, exist_ok=True)

        # Clone the project git repos
        project_info.clone_upstream_git(base_dir=self.upstream_project_directory.parent)
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
    LATEST_TAG = "1.0.0~alpha.7"
    NIGHTLY_MINVER_TAG: str = "1.0.0~alpha.7"

    def __init__(self, directory_info: DirectoryInfo, tag: str | None):
        # Nightly specified if tag not specified
        self.nightly = tag is None
        # If nightly
        commit = "" if self.nightly else str("epoch-" + tag).replace("~", "-")

        if self.nightly:
            print("Nightly, so tag is accessed through rev-parse")
            # When we don't get a specific tag (i.e. nightly), our 'tag' becomes the shortcommit
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=directory_info.upstream_project_directory,
            ).stdout.strip()
            print(f"Commit: {commit}")
            tag = commit[:7]

        self.tag = tag
        self.tag_no_tilde = self.tag.replace("~", "-")

        print("Git reset")
        subprocess.run(
            ["git", "reset", "--hard", commit],
            cwd=directory_info.upstream_project_directory,
        )
        subprocess.run(
            ["git", "checkout", commit], cwd=directory_info.upstream_project_directory
        )

        print("Git rev-parse")
        self.commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=directory_info.upstream_project_directory,
        ).stdout.strip()

        self.commit_date = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d"],
            capture_output=True,
            text=True,
            cwd=directory_info.upstream_project_directory,
        ).stdout.strip()
        self.commit_date_string = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=iso"],
            capture_output=True,
            text=True,
            cwd=directory_info.upstream_project_directory,
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
            ["find", "./vendor", "-name", "*.rs", "-type", "f", "-exec", "chmod", "-x", "{}", "+"],
            cwd=self.directory_info.upstream_project_directory,
            check=False,
        )

    # This function prepares the vendored artifacts for the package
    def vendor(self):
        print("vendor")
        # Run cargo vendor
        cargo_vendor_output = subprocess.run(
            ["cargo", "vendor"],
            capture_output=True,
            text=True,
            cwd=self.directory_info.upstream_project_directory,
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
                "-C",
                self.directory_info.upstream_project_directory,
                "-pczf",
                self.directory_info.output_dir.joinpath(
                    "vendor-" + self.tag_info.tag_no_tilde + ".tar.gz"
                ),
                "vendor",
            ],
            cwd=self.directory_info.output_dir,
        )

    # This function copies files from the fedora upstream rpm source to the output directory
    def copy_fedora_files_to_output(self):
        print("copy_fedora_files_to_output")
        for root, dirs, files in os.walk(self.directory_info.fedora_project_directory):
            relative_path = os.path.relpath(
                root, self.directory_info.fedora_project_directory
            )
            dest_path = os.path.join(self.directory_info.output_dir, relative_path)

            os.makedirs(dest_path, exist_ok=True)  # Ensure destination subdir exists

            for file in files:
                # Skip vendor-config
                if file.count("vendor-config") > 0:
                    continue
                shutil.copy2(
                    os.path.join(root, file), os.path.join(dest_path, file)
                )  # Preserve metadata
        # Don't copy sources (since we have the sources in our directory now presumably)
        self.directory_info.output_dir.joinpath("sources").unlink(missing_ok=True)
        self.directory_info.output_dir.joinpath(
            self.project_info.rpm_name + ".spec"
        ).unlink(missing_ok=True)

    # Prepare the rpm spec repo by applying patches and modifying the spec file
    def prepare_spec_repo(self):
        print("prepare_spec_repo")
        spec_path = self.directory_info.fedora_project_directory.joinpath(
            f"{self.project_info.rpm_name}.spec"
        )
        output_path = self.directory_info.output_dir.joinpath(
            f"{self.project_info.rpm_name}.spec"
        )
        # Apply downstream -nightly patches
        for root, dirs, files in os.walk(self.directory_info.patch_directory):
            for file in files:
                os.path.join(root, file)
                print("Applying patch:", file)
                ot = subprocess.run(
                    [
                        "git",
                        "apply",
                        str(os.path.join(root, file)),
                    ],
                    cwd=self.directory_info.fedora_project_directory,
                    capture_output=True,
                    text=True,
                )
                if ot.returncode != 0:
                    print("Patch failed!\n", ot.stdout.strip(), ot.stderr.strip())

        # Copy the files to the output
        self.copy_fedora_files_to_output()

        # Make spec file modifications
        with open(spec_path, "r") as f:
            spec_res = SpecFile(self.project_info, self.tag_info, f.read())
            with open(output_path, "w") as f2:
                f2.write(spec_res.spec_out)

    # Performs the remainder of setup needed to build the rpm
    def setup(self):
        print("setup")
        # Apply project patches early if this flag is specified
        if self.project_info.apply_patches:
            self.apply_patches_to_repo()
        # If we are building a project that needs vendoring, do that now
        if self.project_info.vendor:
            self.vendor()
        # Finally, prepare the Fedora spec side
        self.prepare_spec_repo()
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
                out_str += f"%global cosmic_minver {TagInfo.NIGHTLY_MINVER_TAG}\n\n"
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
                        f"Version: {TagInfo.NIGHTLY_MINVER_TAG}^git{tag_info.commit_date}.{tag_info.commit[:7]}"
                    )
                    out_line = f"Version: {TagInfo.NIGHTLY_MINVER_TAG}^git%{{commitdate}}.%{{shortcommit}}"
            elif in_line.startswith("Source0: "):
                out_line = out_line.replace("epoch-%{version_no_tilde}", "%{commit}")
            elif in_line.startswith("Release: ") and RELEASE_OVERRIDE:
                out_line = f"Release: {RELEASE_OVERRIDE}"
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
            if (
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


# Define every COSMIC package
PACKAGES: dict[str, ProjectInfo] = {
    "cosmic-app-library": ProjectInfo(
        rpm_name="cosmic-app-library", crate_name="cosmic-applibrary"
    ),
    "cosmic-applets": ProjectInfo(rpm_name="cosmic-applets"),
    "cosmic-bg": ProjectInfo(rpm_name="cosmic-bg"),
    "cosmic-comp": ProjectInfo(rpm_name="cosmic-comp"),
    "cosmic-edit": ProjectInfo(rpm_name="cosmic-edit"),
    "cosmic-files": ProjectInfo(rpm_name="cosmic-files"),
    "cosmic-greeter": ProjectInfo(rpm_name="cosmic-greeter"),
    "cosmic-icon-theme": ProjectInfo(
        rpm_name="cosmic-icon-theme", crate_name="cosmic-icons", vendor=False
    ),
    "cosmic-idle": ProjectInfo(rpm_name="cosmic-idle"),
    "cosmic-launcher": ProjectInfo(rpm_name="cosmic-launcher"),
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
    "cosmic-wallpapers": ProjectInfo(rpm_name="cosmic-wallpapers", vendor=False, zip_self=True),
    "cosmic-workspaces": ProjectInfo(
        rpm_name="cosmic-workspaces", crate_name="cosmic-workspaces-epoch"
    ),
    "xdg-desktop-portal-cosmic": ProjectInfo(rpm_name="xdg-desktop-portal-cosmic"),
    "pop-launcher": ProjectInfo(
        rpm_name="pop-launcher", crate_name="launcher", upstream_tag="1.2.4"
    ),
    # STAGING
    "cosmic-initial-setup": ProjectInfo(rpm_name="cosmic-initial-setup", staging=True, zip_self=True),
}

RELEASE_OVERRIDE = None

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

parser.add_argument("rpm_name", choices=PACKAGES.keys())
parser.add_argument(
    "--tag",
    help="Tag to use. Defaults to latest commit (Nightly). Specify --tag latest to get latest tag",
)
parser.add_argument("--input", help="Input directory (cosmic-packaging repo) to use.")
parser.add_argument("--output", help="Output directory to use.")

###############
# RUN PROGRAM #
###############

args = parser.parse_args()
# Identify project
project_info = PACKAGES[args.rpm_name]
# Get input directory and output directory
# Depends on project_info to get the subdirectory names
# This instantiation will clone the projects into their proper directories as well
directory_info = DirectoryInfo(
    project_info=project_info,
    input_dir=pathlib.Path(args.input) if args.input else pathlib.Path.cwd(),
    output_dir=pathlib.Path(args.output) if args.output else pathlib.Path.cwd(),
)
# Normalize tag argument from the command line
tag = args.tag
if args.tag == "latest":
    tag = TagInfo.LATEST_TAG
elif tag == "nightly":
    tag = None
# Get information about tags, using the cloned project
# This also gets the git project into the correct revision by checking out the proper rev
tag_info = TagInfo(
    directory_info=directory_info,
    tag=tag,
)

project_operations = ProjectOperations(project_info, directory_info, tag_info)
project_operations.setup()

# We are now set up with all the variables we need to prepare the output for rpm building
# Finally, clean up by removing the cloned repos
shutil.rmtree(directory_info.upstream_project_directory)
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
)
print(ls_result.stdout.strip())
