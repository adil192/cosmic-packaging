#!/bin/bash -x

# name of the crate/package
name=$1
# version of the crate/package
version=$2
# commit to target (latest == master)
commit=$3
# path to the spec file on the pc
path_to_spec=$4
# repo link
repo=$5

# Get specfile
cp $path_to_spec $name.spec 2>/dev/null || :

# Make replacements to specfile
sed -i "/^%global ver / s/.*/%global ver $version/" $name.spec
sed -i "/^%global commit / s/.*/%global commit none/" $name.spec
current_date=$(date +'%Y%m%d.%H')
sed -i "/^%global commitdate / s/.*/%global commitdate $current_date/" $name.spec
sed -i "/^%global commitdatestring / s/.*/%global commitdatestring $current_date/" $name.spec


ls -a
pwd

echo Done! $1 $2 $3 $4 $5