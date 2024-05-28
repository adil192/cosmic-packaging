#!/bin/bash -x

VENDOR=1
# Names (Source name can sometimes be the same as name)
NAME=
SOURCE_NAME=
# Version and commit (latest if using master)
VERSION=0.1.0
COMMIT=LATEST
# Repos
REPO=https://github.com/pop-os/$SOURCE_NAME
RPM_REPO=https://pagure.io/forks/ryanabx/fedora-cosmic/cosmic-packaging.git
# Paths to files
RPM_FILES=cosmic-packaging/rpms/$NAME/*
SCRIPT_FILE=srpm.sh
SCRIPT_DIR=cosmic-packaging/scripts/$SCRIPT_FILE

# Clone the RPM repo
git clone --recurse-submodules $RPM_REPO
# Get extra RPM files
cp $RPM_FILES .
# Get script file
cp $SCRIPT_DIR .
# Run script file
. $SCRIPT_FILE $NAME $SOURCE_NAME $VERSION $COMMIT $REPO $VENDOR