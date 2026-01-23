#!/bin/bash -xe

export NAME=cosmic-term

SCRIPT=cosmic-packaging-bootstrap.py
RPM_REPO_NAME=cosmic-packaging
RPM_REPO=https://forge.fedoraproject.org/cosmic/$RPM_REPO_NAME.git

git clone $RPM_REPO
cp $RPM_REPO_NAME/scripts/$SCRIPT .

python3 $SCRIPT $NAME --input $(pwd)/cosmic-packaging --output $(pwd)

rm $SCRIPT
rm -rf $RPM_REPO_NAME

ls -a

cat $NAME.spec
