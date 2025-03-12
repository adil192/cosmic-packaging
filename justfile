set working-directory := 'dev'
set export

NAME := 'cosmic-files'
TAG := 'nightly'

all *FLAGS: clean (init FLAGS) sources spec build

all-srpm *FLAGS: clean (init FLAGS) sources spec build-srpm

# Requires python3
init *FLAGS:
    python3 ../scripts/cosmic-packaging-bootstrap.py {{NAME}} ../rpms/{{NAME}} --cwd . --tag {{TAG}} {{FLAGS}} 

# Make sure rpm tree is setup (rpmdev-setuptree)
# Install rpmdevtools
sources:
    cp vendor-* ~/rpmbuild/SOURCES/
    cp *.patch ~/rpmbuild/SOURCES/ 2>/dev/null || true
    spectool -g -R {{NAME}}.spec

spec:
    cp {{NAME}}.spec ~/rpmbuild/SPECS/

build:
    rpmbuild --undefine=_disable_source_fetch -bb ~/rpmbuild/SPECS/{{NAME}}.spec

build-srpm:
    rpmbuild -bs ~/rpmbuild/SPECS/{{NAME}}.spec

fast-build:
    rpmbuild -bb --short-circuit ~/rpmbuild/SPECS/{{NAME}}.spec

clean:
    rm -rf ./*
    rm -rf ./.*
    touch .keep

clean-rpmbuild-dir:
    rm -rf ~/rpmbuild
    rpmdev-setuptree