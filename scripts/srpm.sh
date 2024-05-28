#!/bin/bash -x

# NAME of the crate/package
NAME=$1
SOURCE_NAME=$2
# VERSION of the crate/package
VERSION=$3
# COMMIT to target (latest == master)
COMMIT=$4
# REPO link
REPO=$5
# VENDOR?
VENDOR=$6

LATEST="LATEST"

# Clone REPO and cd into it
mkdir $SOURCE_NAME-$COMMIT && cd $SOURCE_NAME-$COMMIT && git clone --recurse-submodules $REPO .

# Get latest COMMIT hash if COMMIT is set to latest
if [[ "$COMMIT" == "$LATEST" ]]
then
    COMMIT=$(git rev-parse HEAD)
    cd .. && mv $SOURCE_NAME-latest $SOURCE_NAME-$COMMIT && cd $SOURCE_NAME-$COMMIT
fi

# Reset to specified COMMIT
git reset --hard $COMMIT

if [ "$VENDOR" -eq 1 ]; then
    echo "VENDOR=1"
    # Vendor dependencies and zip vendor
    cargo vendor > ../vendor-config.toml
    tar -pczf vendor.tar.gz vendor && mv vendor.tar.gz ../vendor.tar.gz
    # Back into parent directory
    rm -rf vendor
    cd ..
else
    cd ..
fi

# Zip SOURCE
tar -pczf $SOURCE_NAME-$COMMIT.tar.gz $SOURCE_NAME-$COMMIT
rm -rf $SOURCE_NAME-$COMMIT

# Make replacements to specfile
sed -i "/^%global ver / s/.*/%global ver $VERSION/" $NAME.spec
sed -i "/^%global commit / s/.*/%global commit $COMMIT/" $NAME.spec
current_date=$(date +'%Y%m%d.%H')
sed -i "/^%global date / s/.*/%global date $current_date/" $NAME.spec

# Should have these sources
# SOURCE_NAME-COMMIT.tar.gz
# vendor.tar.gz
# vendor-config.toml