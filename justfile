set working-directory := 'dev'
set export

NAME := 'cosmic-files'
VERSION := '0.1.0'
COMMIT := 'latest'
VENDOR := '1'

all: init sources spec build

init:
    cp ../rpms/{{NAME}}/* .
    ../scripts/srpm.sh

sources:
    cp vendor-* ~/rpmbuild/SOURCES/
    cp *.patch ~/rpmbuild/SOURCES/ 2>/dev/null || true

spec:
    cp ../rpms/{{NAME}}/{{NAME}}.spec .
    VENDOR=0 ../scripts/srpm.sh
    cp {{NAME}}.spec ~/rpmbuild/SPECS/

build:
    rpmbuild --undefine=_disable_source_fetch -bb ~/rpmbuild/SPECS/{{NAME}}.spec

fast-build:
    rpmbuild -bb --short-circuit ~/rpmbuild/SPECS/{{NAME}}.spec

no-source:
    cp ../rpms/{{NAME}}/{{NAME}}.spec .
    ../scripts/no-source-srpm.sh

clean:
    rm -rf ./*
    touch .keep