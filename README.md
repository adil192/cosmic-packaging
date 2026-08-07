# Fedora Packaging Utilities for the COSMIC Desktop Environment

![Fedora COSMIC Logo](https://raw.githubusercontent.com/adil192/cosmic-packaging/refs/heads/main/logo.png)

This copr repo contains tagged releases of COSMIC faster than those in the official Fedora repos.

Use at your own risk!

Our packages apply the following additional patches:
1. **Four finger gestures for app library and workspace overview**
    (https://github.com/pop-os/cosmic-comp/pull/1799)

    This PR has not been accepted upstream yet since they first want to work on their settings UI for gestures.

    It's fine for us to use this patch with these caveats:
    - Behaviour is likely to change once support lands properly upstream.
    - There are no 1-to-1 animations like in GNOME.

### Installation Instructions

Install the [Fedora COSMIC Spin](https://fedoraproject.org/spins/cosmic/) or install COSMIC on another Fedora variant:
```sh
sudo dnf install @cosmic-desktop-environment
```

Then install updates from [my copr repo](https://copr.fedorainfracloud.org/coprs/adil192/cosmic-epoch/):
```sh
sudo dnf copr enable adil192/cosmic-epoch
sudo dnf update
```

### Credits

All of the hard parts of packaging COSMIC are done by @ryanabx's repo here: [https://forge.fedoraproject.org/cosmic/cosmic-packaging](https://forge.fedoraproject.org/cosmic/cosmic-packaging).

All I'm doing is locking it to the latest tagged release.
I can release updates faster than the official packages because mine aren't going through Fedora's review process.

This also means they are less tested, so if you're looking for a rock solid stable desktop, consider sticking to the official packages.
Conversely, if you want the latest and greatest features, consider using [ryanabx's nightly copr packages](https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch/) instead of my copr repo.
