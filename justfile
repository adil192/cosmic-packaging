set working-directory := 'dev'
set export

PACKAGE := 'cosmic-comp'
# REPO := 'https://github.com/pop-os/cosmic-comp.git'
# VERSION := '0.1.0'
# COMMIT := 'latest'

all: init sources spec build

init:
    cp ../rpms/{{PACKAGE}}/* .
    ../scripts/srpm.sh

sources:
    cp vendor-* ~/rpmbuild/SOURCES/
    cp *.patch ~/rpmbuild/SOURCES/ || true

spec:
    cp ../rpms/{{PACKAGE}}/{{PACKAGE}}.spec .
    VENDOR=0 ../scripts/srpm.sh
    cp {{PACKAGE}}.spec ~/rpmbuild/SPECS/

build:
    rpmbuild --undefine=_disable_source_fetch -bb ~/rpmbuild/SPECS/{{PACKAGE}}.spec

fast-build:
    rpmbuild -bb --short-circuit ~/rpmbuild/SPECS/{{PACKAGE}}.spec
