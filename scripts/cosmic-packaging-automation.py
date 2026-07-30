"""Automation script for the Fedora COSMIC packaging workflow.

Handles SSH agent setup, Kerberos authentication, side tag creation,
queuing builds via cosmic-packaging-new-release.py, and monitoring
Koji build status until all packages are complete.
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path


def run_cmd(cmd: list[str], input_data: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the CompletedProcess result."""
    env = dict(__import__("os").environ)
    result = subprocess.run(
        cmd,
        input=input_data,
        text=True,
        env=env,
        check=check,
    )
    return result


def setup_ssh_agent(ssh_key: str, ssh_password: str) -> None:
    """Start ssh-agent and add the given key."""
    ssh_key_path = Path(ssh_key).expanduser()

    if not ssh_key_path.exists():
        print(f"ERROR: SSH key not found at {ssh_key_path}", file=sys.stderr)
        sys.exit(1)

    # Start ssh-agent and capture its output for eval
    agent_output = run_cmd(["ssh-agent", "-s"]).stdout.strip()
    print(f"SSH agent started: {agent_output}")

    # Parse the SSH_AUTH_SOCK and SSH_AGENT_PID from the agent output
    env_vars = {}
    for line in agent_output.splitlines():
        match = re.match(r'export (\w+)="(.+)"', line)
        if match:
            env_vars[match.group(1)] = match.group(2)

    if "SSH_AUTH_SOCK" not in env_vars or "SSH_AGENT_PID" not in env_vars:
        print("ERROR: Failed to parse ssh-agent output", file=sys.stderr)
        sys.exit(1)

    # Export the variables so ssh-add can find the agent
    import os
    os.environ["SSH_AUTH_SOCK"] = env_vars["SSH_AUTH_SOCK"]
    os.environ["SSH_AGENT_PID"] = env_vars["SSH_AGENT_PID"]

    # Add the key by piping the password to ssh-add
    print(f"Adding SSH key: {ssh_key_path}")
    result = subprocess.run(
        ["ssh-add", str(ssh_key_path)],
        input=ssh_password + "\n",
        text=True,
        capture_output=True,
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
    )

    combined_output = result.stdout + result.stderr

    # Check for success indicators
    if result.returncode != 0 or "Ticket cache:" not in combined_output:
        print(
            f"ERROR: Kerberos authentication failed.\nOutput:\n{combined_output}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Kerberos authentication successful.")


def create_side_tag() -> str:
    """Request a new Fedora side tag via fedpkg and return the tag name."""
    print("Requesting a new side tag...")

    result = run_cmd(["fedpkg", "request-side-tag"], check=True)
    output = result.stdout.strip()

    # Parse the side tag from output like:
    # Side tag 'f45-build-side-145093' (id 145093) created.
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


def run_new_release(side_tag: str) -> tuple[bool, list[str]]:
    """Run cosmic-packaging-new-release.py with the given side tag.

    Returns (success, error_list) where success is True if no errors occurred.
    """
    script = Path(__file__).parent / "cosmic-packaging-new-release.py"

    print(f"Running cosmic-packaging-new-release.py with side tag: {side_tag}")

    result = subprocess.run(
        [sys.executable, str(script), "--side-tag", side_tag],
        text=True,
        capture_output=True,
    )

    combined = result.stdout + result.stderr
    print(combined, end="" if combined.endswith("\n") else "\n")

    # Check for errors in the output
    # The script outputs: errors: []
    # We look for the errors line
    errors_match = re.search(r"errors:\s*(\[.*\])", combined)
    errors_list = []
    if errors_match:
        errors_str = errors_match.group(1)
        # Parse the list - it contains strings like 'cosmic-edit f43'
        errors_list = [
            e.strip().strip("'\"") for e in errors_str.strip("[]").split(",") if e.strip()
        ]

    has_errors = result.returncode != 0 or bool(errors_list)
    return not has_errors, errors_list


def check_koji_status() -> str:
    """Run cosmic-packaging-new-release.py --koji-status and return the output.

    Returns the combined stdout/stderr for parsing.
    """
    script = Path(__file__).parent / "cosmic-packaging-new-release.py"

    result = subprocess.run(
        [sys.executable, str(script), "--koji-status"],
        text=True,
        capture_output=True,
    )

    combined = result.stdout + result.stderr
    print(combined, end="" if combined.endswith("\n") else "\n")
    return combined


def parse_koji_status(output: str) -> dict[str, dict[str, tuple[str, str]]]:
    """Parse the Koji status table output.

    Returns a dict mapping package name -> {branch: (version_str, status)}.
    Branches are like 'rawhide', 'f44', 'f43'.
    """
    packages = {}
    # Match lines like:
    # cosmic-app-library                  1.5.0-1 (BUILDING) 1.5.0-1 (BUILDING) 1.5.0-1 (BUILDING)
    # cosmic-osd                          1.4.0-1 (COMPLETE) 1.5.0-1 (BUILDING) 1.5.0-1 (BUILDING)
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


def determine_expected_version(status: dict[str, dict[str, tuple[str, str]]]) -> str | None:
    """Determine the expected version from the Koji status.

    Finds the most common version across all packages and branches.
    """
    versions = []
    for branches in status.values():
        for version_str, _ in branches.values():
            # Extract just the version part (before the -)
            version = version_str.split("-")[0]
            versions.append(version)

    if not versions:
        return None

    # Find the most common version
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
                # Unexpected status (FAILED, CANCELED, etc.)
                has_error = True
            elif version != expected_version:
                # Wrong version
                has_error = True
            elif task_status == "BUILDING":
                has_building = True

    if has_error:
        return "error"
    elif has_building:
        return "building"
    else:
        return "complete"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cosmic-packaging-automation",
        description="Automate the Fedora COSMIC packaging workflow: "
        "SSH/Kerberos setup, side tag creation, build queuing, and Koji monitoring.",
    )

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
    parser.add_argument(
        "--side-tag",
        help="Use this fedpkg side tag instead of generating one",
    )
    parser.add_argument(
        "--error-wait-time",
        type=int,
        default=5,
        help="Time in minutes to wait before retrying on errors in cosmic-packaging-new-release.py (default: 5)",
    )
    parser.add_argument(
        "--koji-wait-time",
        type=int,
        default=10,
        help="Time in minutes to wait between Koji status checks (default: 10)",
    )

    args = parser.parse_args()

    # Validate required args when not skipping setup
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

    # Step 1 & 2: Setup (SSH agent + Kerberos)
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

    # Step 3: Create side tag
    print("=" * 60)
    print("Step 3: Creating side tag...")
    print("=" * 60)
    if args.side_tag:
        side_tag = args.side_tag
        print(f"Using provided side tag: {side_tag}")
    else:
        side_tag = create_side_tag()
    print()

    # Step 4: Run cosmic-packaging-new-release.py
    print("=" * 60)
    print("Step 4: Running cosmic-packaging-new-release.py...")
    print("=" * 60)
    max_retries = 10
    retry_count = 0
    while True:
        success, errors = run_new_release(side_tag)
        if success:
            print("Builds queued successfully.")
            break
        retry_count += 1
        if retry_count >= max_retries:
            print(
                f"ERROR: Max retries ({max_retries}) reached. Errors: {errors}",
                file=sys.stderr,
            )
            sys.exit(1)
        wait_minutes = args.error_wait_time
        wait_seconds = wait_minutes * 60
        print(
            f"Errors detected: {errors}\n"
            f"Waiting {wait_minutes} minutes before retry... "
            f"(Attempt {retry_count}/{max_retries})"
        )
        time.sleep(wait_seconds)
    print()

    # Step 5: Monitor Koji status
    print("=" * 60)
    print("Step 5: Monitoring Koji build status...")
    print("=" * 60)
    wait_minutes = args.koji_wait_time
    wait_seconds = wait_minutes * 60
    max_koji_checks = 100  # Safety limit

    for check_num in range(1, max_koji_checks + 1):
        print(f"\n--- Koji status check #{check_num} ---")
        output = check_koji_status()

        result = evaluate_koji_status(output)

        if result == "complete":
            print()
            print("=" * 60)
            print("SUCCESS: All packages are COMPLETE!")
            print("=" * 60)
            sys.exit(0)
        elif result == "building":
            print(
                f"Some packages are still building. "
                f"Waiting {wait_minutes} minutes before next check..."
            )
            time.sleep(wait_seconds)
        else:
            # Error state - some packages have wrong version or failed status
            print(
                "Packages detected with unexpected status or wrong version. "
                "Rerunning build queue..."
            )
            success, errors = run_new_release(side_tag)
            if not success:
                retry_count += 1
                if retry_count >= max_retries:
                    print(
                        f"ERROR: Max retries ({max_retries}) reached after Koji error. "
                        f"Errors: {errors}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                print(
                    f"Build retry had errors. Waiting {args.error_wait_time} minutes..."
                )
                time.sleep(args.error_wait_time * 60)
            time.sleep(wait_seconds)

    print(
        f"ERROR: Max Koji checks ({max_koji_checks}) reached without completion.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
