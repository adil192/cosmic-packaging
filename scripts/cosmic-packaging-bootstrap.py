import argparse
import subprocess
import pathlib
import os
import shutil
import datetime

packages = {
    "cosmic-app-library": {
        "crate_name": "cosmic-applibrary",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-applets": {
        "crate_name": "cosmic-applets",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-bg": {"crate_name": "cosmic-bg", "vendor": True, "vendor_self": False},
    "cosmic-comp": {"crate_name": "cosmic-comp", "vendor": True, "vendor_self": False},
    "cosmic-edit": {"crate_name": "cosmic-edit", "vendor": True, "vendor_self": True},
    "cosmic-files": {
        "crate_name": "cosmic-files",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-greeter": {
        "crate_name": "cosmic-greeter",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-icon-theme": {"crate_name": "cosmic-icons", "vendor": False},
    "cosmic-idle": {"crate_name": "cosmic-idle", "vendor": True, "vendor_self": False},
    "cosmic-launcher": {
        "crate_name": "cosmic-launcher",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-notifications": {
        "crate_name": "cosmic-notifications",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-osd": {"crate_name": "cosmic-osd", "vendor": True, "vendor_self": False},
    "cosmic-panel": {
        "crate_name": "cosmic-panel",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-player": {
        "crate_name": "cosmic-player",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-randr": {
        "crate_name": "cosmic-randr",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-screenshot": {
        "crate_name": "cosmic-screenshot",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-session": {
        "crate_name": "cosmic-session",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-settings": {
        "crate_name": "cosmic-settings",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-settings-daemon": {
        "crate_name": "cosmic-settings-daemon",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-store": {
        "crate_name": "cosmic-store",
        "vendor": True,
        "vendor_self": False,
    },
    "cosmic-term": {"crate_name": "cosmic-term", "vendor": True, "vendor_self": False},
    "cosmic-wallpapers": {
        "crate_name": "cosmic-wallpapers",
        "vendor": False,
        "vendor_self": False,
    },
    "cosmic-workspaces": {
        "crate_name": "cosmic-workspaces-epoch",
        "vendor": True,
        "vendor_self": False,
    },
    "xdg-desktop-portal-cosmic": {
        "crate_name": "xdg-desktop-portal-cosmic",
        "vendor": True,
        "vendor_self": False,
    },
    "pop-launcher": {"crate_name": "launcher", "vendor": True, "vendor_self": False},
}

POP_OS_GIT = "https://github.com/pop-os/"
NIGHTLY_MINVER_TAG = "1.0.0~alpha.6"

RELEASE_OVERRIDE = f"2"

###########################################
# PATCH EXECUTABLE BIT IN VENDORED CRATES #
###########################################

def patch_vendored_crates():
    global cwd, crate_name
    # XXX: remove me once https://github.com/zip-rs/zip2/pull/238 is merged, and zip is updated in cosmic-{files, xdg-portal, edit}.
    # current version containing the bug: 2.2.0
    subprocess.run(["chmod" "-x" "./vendor/zip/src/spec.rs"], cwd=cwd.joinpath(crate_name), check=False)
    # XXX: remove me once bumpalo > 3.16.0 in cosmic-{edit, files, term}
    subprocess.run(["chmod" "-x" "./vendor/bumpalo/src/lib.rs"], cwd=cwd.joinpath(crate_name), check=False)
    # XXX: cause issue on cosmic-store. I haven't submitted a pull request or anything
    subprocess.run(["chmod" "-x" "./vendor/ipnet/src/lib.rs"], cwd=cwd.joinpath(crate_name), check=False)

############################################
# COPY ALL FILES TO SETUP (EXCEPT SOURCES) #
############################################


def copy_files_to_setup():
    global spec_dir, cwd, crate_name
    for root, dirs, files in os.walk(spec_dir):
        relative_path = os.path.relpath(root, spec_dir)
        dest_path = os.path.join(cwd, relative_path)

        os.makedirs(dest_path, exist_ok=True)  # Ensure destination subdir exists

        for file in files:
            shutil.copy2(
                os.path.join(root, file), os.path.join(dest_path, file)
            )  # Preserve metadata
    # Don't copy sources (since we have the sources in our directory now presumably)
    cwd.joinpath("sources").unlink(missing_ok=True)
    cwd.joinpath(f"{crate_name}.spec").unlink(missing_ok=True)


#############################################
# HANDLE VENDORING OF CARGO DEPENDENDENCIES #
#############################################


def get_vendor_artifacts():
    global rpm_name, crate_name, tag, commit, cwd
    print("VENDOR=1")
    cargo_vendor_output = subprocess.run(
        ["cargo", "vendor"],
        capture_output=True,
        text=True,
        cwd=cwd.joinpath(crate_name),
    )
    with open(
        f"{cwd.joinpath(f"vendor-config-{tag.replace('~', '-')}.toml")}", "w"
    ) as f:
        f.write(cargo_vendor_output.stdout.strip())
    
    patch_vendored_crates()

    tar_cmd = [
        "tar",
        "-C",
        cwd.joinpath(crate_name),
        "-pczf",
        cwd.joinpath(f"vendor-{tag.replace('~', '-')}.tar.gz"),
        "vendor",
    ]
    print(tar_cmd)

    subprocess.run(
        tar_cmd,
        cwd=cwd,
    )


#######################
# SPECFILE PROCESSING #
#######################

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


def process_specfile():
    global rpm_name, spec_dir, tag, cwd, commit, nightly, commit_date, commit_date_string
    spec_path = spec_dir.joinpath(f"{rpm_name}.spec")
    output_path = cwd.joinpath(f"{rpm_name}.spec")
    print(f"Nightly: {nightly}")
    if nightly:
        process_nightly(spec_path, output_path)
    else:
        process_tagged(spec_path, output_path)


def process_nightly(spec_path, output_path):
    global commit, commit_date, commit_date_string, tag, crate_name, rpm_name
    build_date = datetime.datetime.now().strftime("%Y%m%d%H%M")
    with open(spec_path, "r") as f:
        with open(output_path, "w") as f2:
            skip = False
            for in_line in f.readlines():
                out_line = in_line
                if (
                    in_line.startswith(f"%global commit ")
                    or in_line.startswith(
                        f"# While our version corresponds to an upstream tag"
                    )
                ) and not skip:
                    f2.write(
                        f"# cosmic-packaging: Nightly build processed from tagged version at https://src.fedoraproject.org/rpms/{rpm_name}\n"
                    )
                    f2.write(f"%global commit {commit}\n")
                    f2.write(f"%global shortcommit %{{sub %{{commit}} 1 7}}\n")
                    f2.write(f"%global commitdatestring {commit_date_string}\n")
                    f2.write(f"%global commitdate {commit_date}\n")
                    f2.write(f"%global builddate {build_date}\n")
                    f2.write(f"%global cosmic_minver {NIGHTLY_MINVER_TAG}\n\n")
                    skip = True
                elif in_line.startswith(f"Name: "):
                    skip = False
                elif in_line.startswith(f"Version: "):
                    print(
                        f"Version: {NIGHTLY_MINVER_TAG}^git{commit_date}.{commit[:7]}"
                    )
                    out_line = f"Version: {NIGHTLY_MINVER_TAG}^git%{{commitdate}}.%{{shortcommit}}"
                elif in_line.startswith(f"Source0: "):
                    out_line = f"Source0: {POP_OS_GIT}{crate_name}/archive/%{{commit}}/{crate_name}-%{{shortcommit}}.tar.gz"
                elif in_line.startswith(f"Release: "):
                    out_line = f"Release: {RELEASE_OVERRIDE}"
                elif in_line.startswith(f"%autosetup "):
                    out_line = out_line.replace(
                        f"epoch-%{{version_no_tilde}}", f"%{{commit}}"
                    )

                out_line = out_line.replace(
                    f"%{{version_no_tilde}}", f"%{{shortcommit}}"
                )
                if not skip:
                    f2.write(out_line.rstrip() + "\n")


def process_tagged(spec_path, output_path):
    global commit, commit_date, commit_date_string, tag, crate_name, rpm_name
    with open(spec_path, "r") as f:
        with open(output_path, "w") as f2:
            skip = False
            for in_line in f.readlines():
                out_line = in_line
                if (
                    in_line.startswith(f"%global commit ")
                    or in_line.startswith(
                        f"# While our version corresponds to an upstream tag"
                    )
                ) and not skip:
                    f2.write(
                        "# While our version corresponds to an upstream tag, we still need to define\n"
                    )
                    f2.write(
                        "# these macros in order to set the VERGEN_GIT_SHA and VERGEN_GIT_COMMIT_DATE\n"
                    )
                    f2.write(
                        "# environment variables in multiple sections of the spec file.\n"
                    )
                    f2.write(f"%global commit {commit}\n")
                    f2.write(f"%global commitdatestring {commit_date_string}\n")
                    f2.write(f"%global cosmic_minver {tag}\n\n")
                    skip = True
                elif in_line.startswith(f"Name: "):
                    skip = False
                elif in_line.startswith(f"Version: "):
                    out_line = f"Version: {tag}"
                elif in_line.startswith(f"Source0: "):
                    out_line = f"Source0: {POP_OS_GIT}{crate_name}/archive/epoch-%{{version_no_tilde}}/{crate_name}-%{{version_no_tilde}}.tar.gz"
                elif in_line.startswith(f"%autosetup "):
                    out_line = out_line.replace(
                        f"%{{commit}}", f"epoch-%{{version_no_tilde}}"
                    )

                out_line = out_line.replace(
                    f"%{{shortcommit}}", f"%{{version_no_tilde}}"
                )
                if not skip:
                    f2.write(out_line.rstrip() + "\n")


def process_line_tagged(input_line: str):
    global crate_name
    output_line = input_line
    output_line = output_line.replace(f"%{{shortcommit}}", f"%{{version_no_tilde}}")
    if input_line.startswith(f"Version: "):
        output_line = f"Version: {tag}"
    elif input_line.startswith(f"%global commit "):
        output_line = f"%global commit {commit}"
    elif input_line.startswith(f"%autosetup "):
        output_line = output_line.replace(
            f"%{{commit}}", f"epoch-%{{version_no_tilde}}"
        )
    elif input_line.startswith(f"%global shortcommit "):
        output_line = ""
    elif input_line.startswith(f"%global commitdate "):
        output_line = ""
    elif input_line.startswith(f"%global cosmic_minver "):
        output_line = f"%global cosmic_minver {tag}"
    elif input_line.startswith(f"Source0: "):
        # Example: Source0: https://github.com/pop-os/cosmic-workspaces-epoch/archive/epoch-%{version_no_tilde}/cosmic-workspaces-epoch-%{version_no_tilde}.tar.gz
        output_line = f"{POP_OS_GIT}{crate_name}/archive/epoch-%{{version_no_tilde}}/{crate_name}-%{{version_no_tilde}}.tar.gz"
    elif input_line.startswith(f"%global commitdatestring "):
        output_line = f"%global commitdatestring {commit_date_string}"
    return output_line


#################
# CLI ARGUMENTS #
#################

parser = argparse.ArgumentParser(
    prog="cosmic-packaging-bootstrap",
    description="Setup a nightly build of cosmic-packaging",
)

parser.add_argument("rpm_name", choices=packages.keys())
parser.add_argument("spec_dir", help="Path to the directory containing the spec file")
parser.add_argument("--tag", help="Tag to use. Defaults to latest commit (Nightly)")
parser.add_argument(
    "--cwd",
    help="Working directory to use. Defaults to wherever the script was called.",
)

###############
# RUN PROGRAM #
###############

args = parser.parse_args()

rpm_name = args.rpm_name
spec_dir = pathlib.Path(args.spec_dir)
crate_name = packages[rpm_name]["crate_name"]
vendor = packages[rpm_name]["vendor"]
cwd = pathlib.Path(args.cwd) if args.cwd else pathlib.Path.cwd()
tag = args.tag if args.tag else ""
commit = tag
nightly = commit == ""

print(f"RPM Name: {rpm_name}, Crate Name: {crate_name}, Commit: {tag}, Cwd: {cwd}")

if not cwd.exists():
    cwd.mkdir(parents=True, exist_ok=True)

print("Git clone")
subprocess.run(
    [
        "git",
        "clone",
        "--recurse-submodules",
        f"{POP_OS_GIT}{crate_name}.git",
    ],
    cwd=cwd,
)
if tag == "":
    print("Nightly, so tag is accessed through rev-parse")
    # When we don't get a specific tag (i.e. nightly), our 'tag' becomes the shortcommit
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd.joinpath(crate_name),
    ).stdout.strip()
    print(f"Commit: {commit}")
    tag = commit[:7]

print(f"Tag: {tag}")

print("Git reset")
subprocess.run(["git", "reset", "--hard", commit], cwd=cwd.joinpath(crate_name))
subprocess.run(["git", "checkout", commit], cwd=cwd.joinpath(crate_name))

print("Git rev-parse")
commit = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    capture_output=True,
    text=True,
    cwd=cwd.joinpath(crate_name),
).stdout.strip()

print(f"Commit: {commit}")

commit_date = subprocess.run(
    ["git", "log", "-1", f"--format=%cd", f"--date=format:%Y%m%d"],
    capture_output=True,
    text=True,
    cwd=cwd.joinpath(crate_name),
).stdout.strip()
commit_date_string = subprocess.run(
    ["git", "log", "-1", f"--format=%cd", f"--date=iso"],
    capture_output=True,
    text=True,
    cwd=cwd.joinpath(crate_name),
).stdout.strip()

copy_files_to_setup()

if vendor:
    get_vendor_artifacts()

process_specfile()

shutil.rmtree(cwd.joinpath(crate_name))
