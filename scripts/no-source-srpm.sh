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
VERSION=${VERSION:-"0.1.0"}

CURRENT_DATE=$(date +'%Y%m%d')

# Make replacements to specfile
sed -i "/^Version: / s/.*/Version:           $VERSION~^%{CURRENT_DATE}gitnone/" $NAME.spec
