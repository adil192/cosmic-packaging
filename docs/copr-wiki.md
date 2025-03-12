# COSMIC Desktop Environment on Fedora

## Installation (Tagged Releases)

The simplest way to install COSMIC on Fedora is installing from the official repository:

```sh
dnf install @cosmic-desktop-environment
```

This will give you the COSMIC session and everything else required to run the desktop.

## Installation (Nightly releases)

Installing the latest of COSMIC involves installing COSMIC through a COPR

```sh
dnf copr enable ryanabx/cosmic-epoch
dnf install cosmic-desktop
```

## Migration from nightly to tagged releases

Now that the Fedora repos include the latest stable version of COSMIC, it is recommended to use those packages for a more supported experience. If you'd like to migrate, the process is simple!

```sh
dnf remove cosmic-desktop
dnf copr disable ryanabx/cosmic-epoch
dnf install @cosmic-desktop-environment
```

## What is COSMIC?

COSMIC is a next-generation desktop environment primarily developed by System76, and by independent contributors. The desktop is written in rust, and prioritizes modularity for vendors, such that they can create the experience they require for their end-users. The desktop's defaults provide a very slick experience, and Fedora tends to keep these defaults intact. Despite this, the end user can customize COSMIC completely to their liking!