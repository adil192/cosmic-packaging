#!/bin/bash -xe

# Build a package locally.
# Need to be called from the root of the repo (./scripts/build_local.sh)


PACKAGE=cosmic-settings
REPO=https://github.com/pop-os/cosmic-settings

rm -rf dev
mkdir dev
cp rpms/$PACKAGE/* dev/
cp scripts/srpm.sh dev/
cd dev
./srpm.sh $PACKAGE $PACKAGE 0.1.0 LATEST $REPO 1

cp vendor-* ~/rpmbuild/SOURCES/
cp *.patch ~/rpmbuild/SOURCES/ || true

cp $PACKAGE.spec ~/rpmbuild/SPECS/

rpmbuild -bb ~/rpmbuild/SPECS/$PACKAGE.spec
