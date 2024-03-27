#!/bin/bash -x

PACKAGE=
VERSION=0.1.0
COMMIT=latest
REPO=https://github.com/pop-os/$PACKAGE

git clone --recurse-submodules https://pagure.io/forks/ryanabx/fedora-cosmic/cosmic-packaging.git
cp cosmic-packaging/rpms/$PACKAGE/* .
cp cosmic-packaging/scripts/vendor-srpm.sh .
. vendor-srpm.sh $PACKAGE $VERSION $COMMIT $PACKAGE.spec $REPO