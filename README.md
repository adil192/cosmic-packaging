# Fedora Packaging Utilities for the COSMIC Desktop Environment

![Fedora COSMIC Logo](logo.png)

- [Nightly COSMIC Packages](https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch/)

- [Upstream COSMIC Packages](https://src.fedoraproject.org/rpms/cosmic-session)

Be sure to report issues with the packaging in this repo. Report COSMIC related issues in [their repo](https://github.com/pop-os/cosmic-epoch/issues). If unsure whether an issue is with packaging or COSMIC itself, start here, in this repo.

## COSMIC Nightly Packaging Workflow

- Nightly COPR packages are automatically built via a GitHub action on ryanabx's copr automation repo: https://github.com/ryanabx/ryanabx-copr-automation if there is a new commit from the upstream repo.

### Installing nightly packages

Non-Atomic:

```sh
sudo dnf copr enable ryanabx/cosmic-epoch
sudo dnf install cosmic-desktop
```

Atomic (Using Fedora 44 as an example):

```sh
sudo curl https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch/repo/fedora-44/ryanabx-cosmic-epoch-fedora-44.repo -o /etc/yum.repos.d/ryanabx-cosmic-epoch-fedora-44.repo
sudo rpm-ostree override replace --experimental --from repo=copr:copr.fedorainfracloud.org:ryanabx:cosmic-epoch cosmic-app-library cosmic-applets cosmic-bg cosmic-comp cosmic-edit cosmic-files cosmic-greeter cosmic-icon-theme cosmic-idle cosmic-initial-setup cosmic-launcher cosmic-monitor cosmic-notifications cosmic-osd cosmic-panel cosmic-player cosmic-randr cosmic-screenshot cosmic-session cosmic-settings cosmic-settings-daemon cosmic-store cosmic-term cosmic-wallpapers cosmic-workspaces xdg-desktop-portal-cosmic pop-launcher
```

## COSMIC Upstream Packaging Workflow

- New tags are released on `https://github.com/pop-os/`, typically every Tuesday
- A copr build (for https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch-tagged) with the new tags is triggered by an automated action at `https://github.com/ryanabx/ryanabx-copr-automation/`.
    - If any packages fail to build on x86 or aarch64, the package maintainer (ryanabx) will go look through the errors and try to fix problems, and make patches as needed.
- Once all packages build successfully, the package maintainer will trigger the `scripts/cosmic-packaging-new-release.py` script to download the src rpms from the tagged copr and import them into the official repos (`src.fedoraproject.org/rpms/cosmic-*`).
- Fedora Koji builds the COSMIC packages for upstream.
- The package maintainer checks that all builds succeeded, and makes the update at `https://bodhi.fedoraproject.org`.
- Update gets enough karma, and gets released.

---

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
