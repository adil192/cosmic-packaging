#!/bin/bash -xe

# update specfile
#
#
# NAME: package name
# VERSION: tag, semver
# NIGHTLY: 0 or 1

check_variable() {
    local var_name=$1
    if [ -z "${!var_name+x}" ]; then
        echo "Error: '$var_name' is not defined."
        exit 1
    fi
}

check_variable NAME
VERSION=${VERSION:-"1.0.0~alpha.4"}
NIGHTLY=${NIGHTLY:-1}

CURRENT_DATE=$(date +'%Y%m%d')

# Make replacements to specfile
sed -i "/^Version: / s/.*/Version:        ${VERSION}^${CURRENT_DATE}/" $NAME.spec
sed -i "/^%global cosmic_minver / s/.*/%global cosmic_minver $VERSION/" $NAME.spec