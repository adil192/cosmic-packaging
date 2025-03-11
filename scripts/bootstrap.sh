#!/bin/bash -xe

export NAME=cosmic-term

SCRIPT=cosmic-packaging-bootstrap.py
RPM_REPO_NAME=cosmic-packaging
RPM_REPO=https://pagure.io/fedora-cosmic/$RPM_REPO_NAME.git

git clone $RPM_REPO
git -C $(pwd)/$RPM_REPO_NAME submodule update --init --recursive rpms/$NAME
cp $RPM_REPO_NAME/scripts/$SCRIPT .

python3 $SCRIPT $NAME $(pwd)/$RPM_REPO_NAME/rpms/$NAME --cwd $(pwd)

rm $SCRIPT
rm -rf $RPM_REPO_NAME

ls -a

cat $NAME.spec