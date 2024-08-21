#!/bin/bash -xe

# clone repo, detect last commit, vendor deps, update specfile
#
#
# PACKAGE: package name
# SOURCE_NAME: sometime the same of PACKAGE
# VERSION: tag, semver
# COMMIT: latest or sha
# REPO: link
# VENDOR: 0 or 1

check_variable() {
    local var_name=$1
    if [ -z "${!var_name+x}" ]; then
        echo "Error: '$var_name' is not defined."
        exit 1
    fi
}

check_variable PACKAGE
SOURCE_NAME=${SOURCE_NAME:-"$PACKAGE"}
VERSION=${VERSION:-"0.1.0"}
COMMIT=${COMMIT:-"latest"}
REPO=${REPO:-"https://github.com/pop-os/$SOURCE_NAME"}
VENDOR=${VENDOR:-1}

if [ ! -e "$PACKAGE" ]; then
    git clone --recurse-submodules $REPO $PACKAGE
fi

cd $PACKAGE

# Get latest COMMIT hash if COMMIT is set to latest
if [[ "$COMMIT" == "latest" ]]; then
    COMMIT=$(git rev-parse HEAD)
fi

SHORTCOMMIT=$(echo ${COMMIT:0:7})

git reset --hard $COMMIT

COMMITDATE=$(git log -1 --format=%cd --date=format:%Y%m%d)
COMMITDATESTRING=$(git log -1 --format=%cd --date=iso)

if [ "$VENDOR" -eq 1 ]; then
    echo "VENDOR=1"
    # Vendor dependencies and zip vendor
    cargo vendor >../vendor-config-$SHORTCOMMIT.toml
    tar -pczf ../vendor-$SHORTCOMMIT.tar.gz vendor
fi

cd ..

# Make replacements to specfile
sed -i "/^Version: / s/.*/Version:           $VERSION~^%{commitdate}git%{shortcommit}/" $PACKAGE.spec
sed -i "/^%global commit / s/.*/%global commit $COMMIT/" $PACKAGE.spec

sed -i "/^%global commitdate / s/.*/%global commitdate $COMMITDATE/" $PACKAGE.spec
sed -i "/^%global commitdatestring / s/.*/%global commitdatestring $COMMITDATESTRING/" $PACKAGE.spec
