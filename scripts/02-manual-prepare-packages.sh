#!/bin/bash

# Run this from the root of the cosmic-packaging repo!
# You may want to run 01-manual-sync-submodules-with-upstream first!
# If there's vendoring errors, clean your cargo registry by rm -rf ~/.cargo/registry and rm -rf ~/.cargo/git

WORKDIR=~/workdir
TAG=1.0.0~beta.6

list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-player" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "pop-launcher" "xdg-desktop-portal-cosmic")

for item in "${list[@]}"
do
    echo "Processing: $item"
    mkdir -p $WORKDIR/$item
    python3 ./scripts/cosmic-packaging-bootstrap.py --cwd $WORKDIR/$item --tag $TAG $item ./rpms/$item || true
done
