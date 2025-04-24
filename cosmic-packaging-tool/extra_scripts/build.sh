#!/bin/bash

list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-player" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "pop-launcher" "xdg-desktop-portal-cosmic")

echo "WARNING: This will erase everything in ~/workdir. Are you sure about this?"
read v

for item in "${list[@]}"
do
    echo "======================================"
    echo "Processing package $item..."
    rm -rf ~/workdir && mkdir -p ~/workdir
    if cargo run -- setup-build ~/workdir $item --auto-srpm --version 1.0.0~alpha.7; then
        echo "rawhide $item success"
        rm -rf ~/workdir && mkdir -p ~/workdir
        cargo run -- setup-build ~/workdir $item --build-branch f42 --source-branch rawhide && echo "f42 $item success" || true
        rm -rf ~/workdir && mkdir -p ~/workdir
        cargo run -- setup-build ~/workdir $item --build-branch f41 --source-branch rawhide && echo "f41 $item success" || true
    else
        echo "WARNING: rawhide $item failure"
    fi
    echo "======================================"
done
