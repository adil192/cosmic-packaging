#!/bin/bash -x

PACKAGE=

git clone --recurse-submodules https://pagure.io/fedora-cosmic/cosmic-packaging.git
cd cosmic-rpms/$PACKAGE
. ./srpm.sh