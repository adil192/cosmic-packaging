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
# list=("cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-player" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "pop-launcher" "xdg-desktop-portal-cosmic")

rm -rf ./.out
mkdir -p ./.out

function build_package() {
    pkg=$1
    echo "======================================"
    echo "Processing: $pkg"
    rm -f ~/workdir/$pkg.src.rpm
    rm -rf ~/workdir/$pkg/
    python3 ./scripts/cosmic-packaging-new-release.py $pkg > ./.out/log-$item.txt
    rm -f ~/workdir/$pkg.src.rpm
    rm -rf ~/workdir/$pkg/
    echo "======================================"
}

for item in "${list[@]}"
do
    build_package $item
done