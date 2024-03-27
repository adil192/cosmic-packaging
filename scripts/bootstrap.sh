#!/bin/bash -x

PACKAGE=
REPO=https://github.com/pop-os/$PACKAGE

git clone --recurse-submodules https://pagure.io/forks/ryanabx/fedora-cosmic/cosmic-packaging.git
cp cosmic-packaging/rpms/$PACKAGE/* .
cp cosmic-packaging/scripts/vendor-srpm.sh .
. vendor-srpm.sh $PACKAGE 0.1.0 latest $PACKAGE.spec $REPO