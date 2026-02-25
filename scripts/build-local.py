# Build RPM locally
import argparse
import pathlib
import subprocess
import os
import sys

RAWHIDE_NUMBER = "45"

script_directory = pathlib.Path(__file__).parent.resolve()

parser = argparse.ArgumentParser(prog="Local COSMIC RPM Build")

parser.add_argument("rpm_name", help="Name of the RPM to build")
parser.add_argument(
    "version", help="Name of the version to build ('nightly' for nightly)"
)
parser.add_argument(
    "-w",
    "--work_dir",
    type=pathlib.Path,
    help="Name of the working directory (Default='~/workdir/work')",
)
parser.add_argument(
    "-o",
    "--output_dir",
    type=pathlib.Path,
    help="Name of the output directory (Default='~/workdir/output')",
)
parser.add_argument(
    "-b",
    "--build_rpm",
    action="store_true",
    help="Build the RPM from SRPM? (Default='false')",
)

args = parser.parse_args()

if args.work_dir is None:
    work_dir = pathlib.Path.home().joinpath("workdir").joinpath("work").absolute()
else:
    work_dir = args.work_dir.absolute()

if args.output_dir is None:
    output_dir = pathlib.Path.home().joinpath("workdir").joinpath("output").absolute()
else:
    output_dir = args.output_dir.absolute()

print(
    f"Building '{args.rpm_name}' with version '{args.version}' and working directory '{work_dir}'"
)

spec_path = work_dir.joinpath(f"{args.rpm_name}.spec")

os.makedirs(work_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# Bootstrap
subprocess.run(
    [
        "python3",
        script_directory.joinpath("cosmic-packaging-bootstrap.py"),
        "--tag",
        args.version,
        "--input",
        script_directory.parent,
        "--output",
        work_dir,
        args.rpm_name,
    ],
    cwd=script_directory.parent,
)

# Download additional sources
subprocess.run(
    [
        "spectool",
        "-g",
        spec_path,
        "--directory",
        work_dir,
    ],
    cwd=script_directory.parent,
)

print("Building SRPM")
# Run Mock
subprocess.run(
    [
        "mock",
        "-r",
        "fedora-rawhide-x86_64",
        "--buildsrpm",
        "--spec",
        spec_path,
        "--sources",
        work_dir,
        "--resultdir",
        output_dir,
    ]
)

if args.build_rpm:
    print("Building RPM")
    src_rpm_dir = output_dir.joinpath(
        f"{args.rpm_name}-{args.version}-1.fc{RAWHIDE_NUMBER}.src.rpm"
    )
    # Run Mock Again
    try:
        subprocess.run(
            [
                "mock",
                "-r",
                "fedora-rawhide-x86_64",
                "rebuild",
                src_rpm_dir,
            ],
            check=True,
        )
        print("Success")
    except Exception as e:
        print(f"Failed to build RPM: {e}")
        sys.exit(1)
