#!/bin/bash -xe

# update specfile
#
#
# NAME: package name
# VERSION: tag, semver

check_variable() {
    local var_name=$1
    if [ -z "${!var_name+x}" ]; then
        echo "Error: '$var_name' is not defined."
        exit 1
    fi
}

check_variable NAME
VERSION=${VERSION:-"1.0.0~alpha.2"}
NIGHTLY=${NIGHTLY:-1}

CURRENT_DATE=$(date +'%Y%m%d')

# Make replacements to specfile
if [ "$NIGHTLY" -eq 1 ]; then
    echo "NIGHTLY=1"
    sed -i "/^Version: / s/.*/Version:        ${VERSION}/" $NAME.spec
else  
    sed -i "/^Version: / s/.*/Version:        ${VERSION}^${CURRENT_DATE}/" $NAME.spec
fi
