#!/bin/bash -xe

export PACKAGE=cosmic-comp

git clone https://pagure.io/fedora-cosmic/cosmic-packaging.git
cp cosmic-packaging/rpms/$PACKAGE/* .
cp cosmic-packaging/scripts/srpm.sh .

./srpm.sh
