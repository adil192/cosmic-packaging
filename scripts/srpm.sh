#!/bin/bash -xe

# clone repo, detect last commit, vendor deps, update specfile
#
#
# NAME: package name
# SOURCE_NAME: sometime the same of NAME
# VERSION: tag, semver
# COMMIT: latest or sha
# REPO: link
# VENDOR: 0 or 1
# NIGHTLY: 0 or 1
# VENDORSELF: 0 or 1

check_variable() {
    local var_name=$1
    if [ -z "${!var_name+x}" ]; then
        echo "Error: '$var_name' is not defined."
        exit 1
    fi
}

check_variable NAME
SOURCE_NAME=${SOURCE_NAME:-"$NAME"}
VERSION=${VERSION:-"1.0.0~alpha.5.1"}
VERSION_NO_TILDE=$(echo "$VERSION" | sed 's/~/-/g')
COMMIT=${COMMIT:-"latest"}
REPO=${REPO:-"https://github.com/pop-os/$SOURCE_NAME"}
VENDOR=${VENDOR:-1}
VENDORSELF=${VENDORSELF:-0}
NIGHTLY=${NIGHTLY:-1}

if [ "$NIGHTLY" -eq 0 ]; then
    COMMIT="epoch-1.0.0-alpha.5.1"
fi

if [ ! -e "$NAME" ]; then
    git clone --recurse-submodules $REPO $NAME
fi

cd $NAME

# Get latest COMMIT hash if COMMIT is set to latest
if [[ "$COMMIT" == "latest" ]]; then
    COMMIT=$(git rev-parse HEAD)
fi

git reset --hard $COMMIT

# Ensure commit is set to the current head of the local repo
# This is needed because if we reset to a tag, we want the commit to be in the commit field later on (for VERGEN)
COMMIT=$(git rev-parse HEAD)
SHORTCOMMIT=$(echo ${COMMIT:0:7})

COMMITDATE=$(git log -1 --format=%cd --date=format:%Y%m%d)
COMMITDATESTRING=$(git log -1 --format=%cd --date=iso)

if [ "$VENDOR" -eq 1 ]; then
    for file in ../*.patch; do
        # Check if the glob found any files
        if [ -f "$file" ]; then
            echo "Patching with $file"
            # Add your processing commands here
            git apply $file
        fi
    done

    cargo generate-lockfile

    echo "VENDOR=1"
    # Vendor dependencies and zip vendor
    if [ "$NIGHTLY" -eq 1 ]; then
        cargo vendor >../vendor-config-$SHORTCOMMIT.toml
    else
        cargo vendor >../vendor-config-$VERSION_NO_TILDE.toml
    fi
    
    # XXX: remove me once https://github.com/zip-rs/zip2/pull/238 is merged, and zip is updated in cosmic-{files, xdg-portal, edit}.
    # current version containing the bug: 2.2.0
    chmod -x ./vendor/zip/src/spec.rs || true

    # XXX: remove me once bumpalo > 3.16.0 in cosmic-{edit, files, term}
    chmod -x ./vendor/bumpalo/src/lib.rs || true

    # XXX: cause issue on cosmic-store. I haven't submitted a pull request or anything
    chmod -x ./vendor/ipnet/src/lib.rs || true
    if [ "$NIGHTLY" -eq 1 ]; then
        tar -pczf ../vendor-$SHORTCOMMIT.tar.gz vendor
    else
        tar -pczf ../vendor-$VERSION_NO_TILDE.tar.gz vendor
    fi
fi

cd ..

if [ "$VENDORSELF" -eq 1 ]; then
    if [ "$NIGHTLY" -eq 1 ]; then
	    tar -pczf $NAME-archive-$SHORTCOMMIT.tar.gz $NAME
    else
        tar -pczf $NAME-archive-$VERSION_NO_TILDE.tar.gz $NAME
    fi
fi

# Make replacements to specfile
if [ "$NIGHTLY" -eq 1 ]; then
    echo "NIGHTLY=1"
    sed -i "/^Version: / s/.*/Version:        $VERSION^git%{commitdate}.%{shortcommit}/" $NAME.spec
    sed -i "/^%global commitdate / s/.*/%global commitdate $COMMITDATE/" $NAME.spec
    sed -i "/^%global commit / s/.*/%global commit $COMMIT/" $NAME.spec
else
    sed -i "/^Version: / s/.*/Version:        $VERSION/" $NAME.spec
    # Replace shortcommit with version_no_tilde and delete shortcommit def. version_no_tilde is predefined by rpm macros
    sed -i "/^%global shortcommit /d" $NAME.spec
    # Replace commit in Source0 with epoch-%version_no_tilde
    sed -i "/^Source0/ s/%{commit}/epoch-%{version_no_tilde}/g" $NAME.spec
    sed -i "/^%autosetup/ s/%{commit}/epoch-%{version_no_tilde}/g" $NAME.spec
    sed -i "s/%{shortcommit}/%{version_no_tilde}/g" $NAME.spec
    # Delete commitdate, we don't need it here
    sed -i "/^%global commitdate /d" $NAME.spec
    # We still need commit, add comments explaining why
    sed -i "/^%global commit / s/.*/\# While our version corresponds to an upstream tag, we still need to define\n\# these macros in order to set the VERGEN_GIT_SHA and VERGEN_GIT_COMMIT_DATE\n\# environment variables in multiple sections of the spec file.\n%global commit $COMMIT/" $NAME.spec
fi
# Universal replacements - Define cosmic_minver and commitdatestring
sed -i "/^%global cosmic_minver / s/.*/%global cosmic_minver $VERSION/" $NAME.spec
sed -i "/^%global commitdatestring / s/.*/%global commitdatestring $COMMITDATESTRING/" $NAME.spec
