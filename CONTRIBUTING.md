# Contributing to cosmic-packaging

## Making patches

The `patches/` directory contains patches specific to the SPEC source repo, not the upstream repository. For example, to patch the upstream repo in the specfile for `cosmic-session`:

- Clone the Fedora source: `git clone https://src.fedoraproject.org/rpms/cosmic-session`.
- Clone the upstream source: `git clone https://github.com/pop-os/cosmic-session`, make your change in the repo, commit it, run `git format-patch -1`, and copy the patch to the Fedora source, and include it as a patch in the specfile:

```spec
Patch1: 0001-my-awesome-patch.patch
```

- Then, make a commit to the Fedora source repo, and make a patch out of that with `git format-patch`.
- Copy that patch into the `patches/cosmic-session` directory, and it will automatically be picked up by the copr build.

## Important scripts

- `scripts/cosmic-packaging-bootstrap.py`: Used by the copr repositories to set up the SRPM sources, handling vendoring of rust dependencies and patch application.
- `scripts/cosmic-packaging-new-release.py`: Used by the package maintainer to download src rpms from the tagged repo, and queue them for building in Koji.

## Verify changes when modifying python scripts

To verify python3 syntax is correct, use `py_compile`

```sh
python3 -m py_compile /path/to/script.py
```
