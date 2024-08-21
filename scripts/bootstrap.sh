#!/bin/bash -xe

export NAME=cosmic-term

SCRIPT=srpm.sh
RPM_REPO=https://pagure.io/fedora-cosmic/cosmic-packaging.git
RPM_REPO_NAME=cosmic-packaging

git clone $RPM_REPO
cp $RPM_REPO_NAME/rpms/$NAME/* .
cp $RPM_REPO_NAME/scripts/$SCRIPT .

./$SCRIPT
