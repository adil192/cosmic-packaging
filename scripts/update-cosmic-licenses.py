#!/usr/bin/env python3
"""
Update licenses in cosmic-* specfiles by fetching the actual license text
from the Rust source repositories using `cargo license`.
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from cosmic_common import PACKAGES

SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
PATCHES_DIR = SCRIPT_DIR.parent / "patches"

# Packages that are explicitly NOT Rust (skip these)
NON_RUST_PACKAGES = {
    "cosmic-wallpapers",
    "cosmic-sound-theme",
    "cosmic-icon-theme",
}

# Normalize legacy/non-SPDX license identifiers to SPDX-compatible forms.
# Negative lookahead (?!\s*(?:-only|-or-later)) ensures GPL-3.0-only is not
# turned into GPL-3.0-only-only, and GPL-2.0-or-later is not corrupted.
LICENSE_NORMALIZATION = [
    (re.compile(r"LGPL-3\.0(?!\s*(?:-only|-or-later))"), "LGPL-3.0-only"),
    (re.compile(r"GPL-3\.0(?!\s*(?:-only|-or-later))"), "GPL-3.0-only"),
    (re.compile(r"LGPL-2\.0(?!\s*(?:-only|-or-later))"), "LGPL-2.0-only"),
    (re.compile(r"GPL-2\.0(?!\s*(?:-only|-or-later))"), "GPL-2.0-only"),
]


def normalize_license(license_str: str) -> str:
    """Normalize legacy license identifiers to SPDX-compatible forms.

    Handles OR expressions correctly by applying normalization to each
    license within the expression, e.g.:
        "GPL-2.0 OR MIT" -> "GPL-2.0-only OR MIT"
        "MIT AND (GPL-3.0 OR Apache-2.0)" -> "MIT AND (GPL-3.0-only OR Apache-2.0)"
    """
    for pattern, replacement in LICENSE_NORMALIZATION:
        license_str = pattern.sub(replacement, license_str)
    return license_str


def check_cargo_license() -> None:
    """Check if cargo-license is installed."""
    try:
        subprocess.run(
            ["cargo-license", "--help"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        print(
            "cargo-license is not installed. Please install it by running:\n"
            "  cargo install cargo-license",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(
            f"cargo-license returned an error: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_rust_licenses(repo_dir: pathlib.Path) -> str:
    """
    Run cargo-license on the given repo directory and return the
    combined license string.
    """
    cmd = [
        "cargo-license",
        "--avoid-build-deps",
        "--avoid-dev-deps",
        "--avoid-proc-macros",
        "--json",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(repo_dir),
    )
    if result.returncode != 0:
        print(
            f"  WARNING: cargo-license failed for {repo_dir}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return ""

    # Parse the JSON and extract licenses, then combine them
    # The jq/awk pipeline from the spec:
    #   jq -r '.[] | .license? // empty | gsub(" AND "; "\n")'
    #   | awk '/^\(.*\)$/ { print; next } / OR / { print "(" $0 ")" ; next } { print }'
    #   | sort -u
    #   | awk 'NR==1 { printf "%s", $0; next } { printf " AND %s", $0 } END { print "" }'

    licenses_data = json.loads(result.stdout)
    all_licenses = []

    for entry in licenses_data:
        license_str = entry.get("license", "")
        if not license_str:
            continue
        # Split " AND " into separate licenses
        parts = license_str.split(" AND ")
        all_licenses.extend(parts)

    if not all_licenses:
        return ""

    # Normalize: wrap licenses containing "OR" in parentheses (if not already wrapped)
    normalized = []
    for lic in all_licenses:
        lic = lic.strip()
        if not lic:
            continue
        if " OR " in lic and not (lic.startswith("(") and lic.endswith(")")):
            lic = f"({lic})"
        normalized.append(lic)

    # Deduplicate and sort
    unique_licenses = sorted(set(normalized))

    # Join with " AND "
    combined = " AND ".join(unique_licenses)

    # Normalize legacy license identifiers to SPDX-compatible forms
    combined = normalize_license(combined)

    return combined


def clone_or_pull(repo_url: str, target_dir: pathlib.Path) -> None:
    """Clone a git repo, or pull if it already exists and is a git repo."""
    is_git_repo = (
        target_dir.exists()
        and (target_dir / ".git").exists()
    )
    if is_git_repo:
        subprocess.run(
            ["git", "-C", str(target_dir), "pull"],
            check=True,
        )
    else:
        # Clean up any existing non-git directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        subprocess.run(
            ["git", "clone", repo_url, str(target_dir)],
            check=True,
        )


def update_spec_license(
    spec_path: pathlib.Path,
    new_license: str,
) -> bool:
    """
    Update the License: line in a specfile.
    Returns True if the license was changed.
    """
    if not spec_path.exists():
        print(f"  WARNING: specfile not found: {spec_path}", file=sys.stderr)
        return False

    content = spec_path.read_text()
    lines = content.splitlines(True)

    new_lines = []
    changed = False

    for line in lines:
        stripped = line.strip()
        # Match "License: " or "License: Value"
        if stripped.startswith("License: "):
            if new_license and stripped != f"License: {new_license}":
                new_lines.append(f"License: {new_license}\n")
                changed = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if changed:
        spec_path.write_text("".join(new_lines))
        print(f"  License updated in {spec_path}")

    return changed


def create_git_patch(
    repo_dir: pathlib.Path,
    patch_path: pathlib.Path,
) -> None:
    """Create a git patch from the current changes in the repo."""
    subprocess.run(
        ["git", "-C", str(repo_dir), "add", "."],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", "Update license"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "format-patch",
            "HEAD~1",
            "-o",
            str(patch_path.parent),
        ],
        check=True,
    )
    # The patch file is named like 0001-Update-license.patch
    # Move/rename it to update-license.patch
    patch_files = sorted(patch_path.parent.glob("0001-*.patch"))
    if patch_files:
        patch_files[0].rename(patch_path)


def parse_spec_file(spec_path: pathlib.Path) -> tuple[str, str | None]:
    """Parse a spec file to extract the package name and URL.

    Returns (name, url) tuple. URL may be None if not found.
    """
    name = None
    url = None

    content = spec_path.read_text()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("Name: "):
            name = stripped[len("Name: "):].strip()
        elif stripped.startswith("URL: "):
            url = stripped[len("URL: "):].strip()

    return name, url


def extract_repo_url(github_url: str) -> tuple[str, str]:
    """Extract the git clone URL from a GitHub web URL.

    Handles both https://github.com/org/repo and
    https://github.com/org/repo.git formats.

    Returns (clean_url, git_url) tuple.
    """
    # Remove trailing / if present
    clean_url = github_url.rstrip("/")
    # Ensure it ends with .git for cloning
    git_url = clean_url + ".git"
    return clean_url, git_url


def process_single_spec(
    spec_path: pathlib.Path,
    dry_run: bool = False,
) -> None:
    """Process a single spec file: parse URL, clone repo, get license, update spec."""
    print(f"\n{'=' * 60}")
    print(f"Processing spec: {spec_path}")

    # --- Step 1: Parse spec file ---
    pkg_name, github_url = parse_spec_file(spec_path)
    if not pkg_name:
        print("  ERROR: Could not extract package name from spec file.", file=sys.stderr)
        sys.exit(1)

    if not github_url:
        print("  ERROR: Could not extract URL from spec file.", file=sys.stderr)
        sys.exit(1)

    print(f"  Package name: {pkg_name}")
    print(f"  GitHub URL: {github_url}")

    clean_url, git_url = extract_repo_url(github_url)

    # --- Step 2: Clone GitHub repo and get licenses ---
    github_dir = pathlib.Path(tempfile.mkdtemp(prefix="cosmic-license-update-"))
    try:
        print(f"  Cloning GitHub repo: {git_url}")
        try:
            clone_or_pull(git_url, github_dir)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR: Failed to clone GitHub repo: {e}", file=sys.stderr)
            sys.exit(1)

        print("  Fetching license information...")
        new_license = get_rust_licenses(github_dir)
        if not new_license:
            print("  WARNING: Could not determine licenses, skipping.")
            return

        print(f"  New license: {new_license}")

        # --- Step 3: Update spec file ---
        # Read current license for comparison
        old_license = None
        for line in spec_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("License: "):
                old_license = stripped[len("License: "):]
                break

        if dry_run:
            if old_license != new_license:
                print(f"  [DRY RUN] Would update license from:")
                print(f"    {old_license}")
                print(f"    to:")
                print(f"    {new_license}")
            else:
                print(f"  [DRY RUN] License is already up to date.")
            return

        changed = update_spec_license(spec_path, new_license)

        if not changed:
            print(f"  License is already up to date.")
            return

        # --- Step 4: Validate SPDX expression ---
        print("  Validating license expression with spdx-tools...")
        try:
            from license_expression import ExpressionParseError
            from spdx_tools.common.spdx_licensing import (
                spdx_licensing,
            )

            try:
                spdx_licensing.parse(new_license, validate=True, strict=True)
                print("  SPDX expression is valid.")
            except ExpressionParseError as spdx_err:
                print(
                    f"  WARNING: SPDX expression is invalid:\n{spdx_err}",
                    file=sys.stderr,
                )
        except ImportError:
            print(
                "  WARNING: spdx-tools not installed, skipping SPDX validation. Install with: pip install spdx-tools license-expression",
                file=sys.stderr,
            )

        # --- Step 5: Validate with rpmlint ---
        print("  Validating specfile with rpmlint...")
        try:
            result = subprocess.run(
                ["rpmlint", str(spec_path)],
                capture_output=True,
                text=True,
            )
            rpmlint_output = result.stdout.strip()
            if result.returncode != 0:
                print(
                    f"  WARNING: rpmlint found issues:\n{rpmlint_output}",
                    file=sys.stderr,
                )
            elif rpmlint_output:
                print(f"  rpmlint output:\n{rpmlint_output}", file=sys.stderr)
            else:
                print("  rpmlint passed.")
        except FileNotFoundError:
            print(
                "  WARNING: rpmlint not found, skipping validation.",
            )

        print(f"  License updated successfully!")

    finally:
        # Clean up temp directory
        shutil.rmtree(github_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update licenses in cosmic-* specfiles"
    )
    parser.add_argument(
        "--package",
        nargs="+",
        choices=list(PACKAGES.keys()),
        help="Specific package(s) to update (default: all cosmic-* Rust packages)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--spec",
        type=pathlib.Path,
        help="Path to a single spec file to update (bypasses default behavior)",
    )
    args = parser.parse_args()

    check_cargo_license()

    # If --spec is provided, process only that spec file
    if args.spec:
        if not args.spec.exists():
            print(f"ERROR: Spec file not found: {args.spec}", file=sys.stderr)
            sys.exit(1)

        process_single_spec(args.spec, dry_run=args.dry_run)
        return

    # Determine which packages to process
    if args.package:
        packages_to_process = args.package
    else:
        # Default: all cosmic-* packages that are Rust-based
        packages_to_process = [
            name
            for name in PACKAGES
            if name not in NON_RUST_PACKAGES
        ]

    print(
        f"Processing {len(packages_to_process)} package(s): {', '.join(packages_to_process)}"
    )

    with tempfile.TemporaryDirectory(prefix="cosmic-license-update-") as tmpdir:
        work_dir = pathlib.Path(tmpdir)

        for pkg_name in packages_to_process:
            github_repo = PACKAGES[pkg_name]
            print(f"\n{'=' * 60}")
            print(f"Processing: {pkg_name} (github: {github_repo})")

            # --- Step 1: Clone GitHub repo and get licenses ---
            github_dir = work_dir / "github" / github_repo
            github_dir.parent.mkdir(parents=True, exist_ok=True)

            print(f"  Cloning GitHub repo: https://github.com/pop-os/{github_repo}")
            try:
                clone_or_pull(
                    f"https://github.com/pop-os/{github_repo}.git",
                    github_dir,
                )
            except subprocess.CalledProcessError as e:
                print(f"  ERROR: Failed to clone GitHub repo: {e}", file=sys.stderr)
                continue

            print("  Fetching license information...")
            new_license = get_rust_licenses(github_dir)
            if not new_license:
                print("  WARNING: Could not determine licenses, skipping.")
                continue

            print(f"  New license: {new_license}")

            # --- Step 2: Clone Fedora RPM repo and update spec ---
            fedora_dir = work_dir / "fedora" / pkg_name
            fedora_dir.parent.mkdir(parents=True, exist_ok=True)

            print(
                f"  Cloning Fedora RPM repo: https://src.fedoraproject.org/rpms/{pkg_name}"
            )
            try:
                clone_or_pull(
                    f"https://src.fedoraproject.org/rpms/{pkg_name}.git",
                    fedora_dir,
                )
            except subprocess.CalledProcessError as e:
                print(f"  ERROR: Failed to clone Fedora repo: {e}", file=sys.stderr)
                continue

            spec_path = fedora_dir / f"{pkg_name}.spec"
            if not spec_path.exists():
                # Try finding the spec file
                spec_files = list(fedora_dir.glob("*.spec"))
                if spec_files:
                    spec_path = spec_files[0]
                else:
                    print(f"  WARNING: No specfile found for {pkg_name}, skipping.")
                    continue

            # Read current license for comparison
            old_license = None
            for line in spec_path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("License: "):
                    old_license = stripped[len("License: "):]
                    break

            if args.dry_run:
                if old_license != new_license:
                    print(f"  [DRY RUN] Would update license from:")
                    print(f"    {old_license}")
                    print(f"    to:")
                    print(f"    {new_license}")
                else:
                    print(f"  [DRY RUN] License is already up to date.")
                continue

            changed = update_spec_license(spec_path, new_license)

            if not changed:
                print(f"  License is already up to date.")
                continue

            # --- Step 3: Validate SPDX expression ---
            print("  Validating license expression with spdx-tools...")
            try:
                from license_expression import ExpressionParseError
                from spdx_tools.common.spdx_licensing import (
                    spdx_licensing,
                )

                try:
                    spdx_licensing.parse(new_license, validate=True, strict=True)
                    print("  SPDX expression is valid.")
                except ExpressionParseError as spdx_err:
                    print(
                        f"  WARNING: SPDX expression is invalid:\n{spdx_err}",
                        file=sys.stderr,
                    )
                    continue
            except ImportError:
                print(
                    "  WARNING: spdx-tools not installed, skipping SPDX validation. Install with: pip install spdx-tools license-expression",
                    file=sys.stderr,
                )
                continue

            # --- Step 4: Validate with rpmlint ---
            print("  Validating specfile with rpmlint...")
            try:
                result = subprocess.run(
                    ["rpmlint", str(spec_path)],
                    capture_output=True,
                    text=True,
                )
                rpmlint_output = result.stdout.strip()
                if result.returncode != 0:
                    print(
                        f"  WARNING: rpmlint found issues:\n{rpmlint_output}",
                        file=sys.stderr,
                    )
                elif rpmlint_output:
                    print(f"  rpmlint output:\n{rpmlint_output}", file=sys.stderr)
                else:
                    print("  rpmlint passed.")
            except FileNotFoundError:
                print(
                    "  WARNING: rpmlint not found, skipping validation.",
                )

            # --- Step 5: Create patch ---
            patch_dir = PATCHES_DIR / pkg_name
            patch_dir.mkdir(parents=True, exist_ok=True)
            patch_path = patch_dir / "update-license.patch"

            print(f"  Creating patch at {patch_path}")
            try:
                create_git_patch(fedora_dir, patch_path)
            except subprocess.CalledProcessError as e:
                print(f"  ERROR: Failed to create patch: {e}", file=sys.stderr)
                continue

            print(f"  Patch created successfully!")

    print(f"\n{'=' * 60}")
    print("Done! Check the patches/ directory for generated patches.")


if __name__ == "__main__":
    main()
