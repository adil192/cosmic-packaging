#!/bin/sh

list=(
    "cosmic-app-library"
    "cosmic-applets"
    "cosmic-bg"
    "cosmic-comp"
    "cosmic-edit"
    "cosmic-files"
    "cosmic-greeter"
    "cosmic-icon-theme"
    "cosmic-idle"
    "cosmic-initial-setup"
    "cosmic-launcher"
    "cosmic-notifications"
    "cosmic-osd"
    "cosmic-panel"
    "cosmic-player"
    "cosmic-randr"
    "cosmic-screenshot"
    "cosmic-session"
    "cosmic-settings"
    "cosmic-settings-daemon"
    "cosmic-store"
    "cosmic-term"
    "cosmic-wallpapers"
    "cosmic-workspaces"
    "pop-launcher"
    "xdg-desktop-portal-cosmic"
    )

rm -rf ./.out
mkdir -p ./.out

# BEFORE RUNNING: MAKE SURE TO `fkinit`
# fkinit -u ryanabx (For example)

function build_package() {
    pkg=$1
    SIDE_TAG=f44-build-side-123334 # MODIFY THIS WITH NEW SIDE TAGS EACH CYCLE
    echo "Processing: $pkg"
    rm -f ~/workdir/$pkg.src.rpm
    rm -rf ~/workdir/$pkg/
    python3 ./scripts/cosmic-packaging-new-release.py $pkg --side-tag $SIDE_TAG > ./.out/log-$item.txt
    rm -f ~/workdir/$pkg.src.rpm
    rm -rf ~/workdir/$pkg/
    echo "Done: $pkg"
}

max_jobs=10

for item in "${list[@]}"
do
    build_package $item &
    (( $(jobs -r | wc -l) >= max_jobs )) && wait -n
done

wait
