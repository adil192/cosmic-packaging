# Nightly Fedora COSMIC Builds

The nightly Fedora COSMIC builds are hosted on the [ryanabx/cosmic-epoch COPR](https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch)

## How are the nightly packages built

Each package in the copr runs the `bootstrap.sh` script, which in turn calls the `cosmic-packaging-bootstrap.py` script, which prepares the sources for the srpm. From there, copr takes over and builds the resulting srpm.

## How to patch nightly packages

Nightly packages now use the upsteam https://src.fedoraproject.org/group/cosmic-sig repos. The patches are hosted in this repo, in [patches](./../patches).
You can use the justfile file to help you.

1. Set the NAME env variable
   - bash: `NAME=cosmic-initial-setup`
   - fish: `set -gx NAME cosmic-initial-setup`
2. Call `just clone-upstream`
3. Make your change
4. Call `just create-patch "commit msg" patch_name`.
