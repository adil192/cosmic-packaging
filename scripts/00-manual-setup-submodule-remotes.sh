#!/bin/bash

# Run this from the root of the cosmic-packaging repo!
# If you haven't ran 00-manual-setup-submodule-remotes.sh, go ahead and do so!
# You only need to run 00-manual-setup-submodule.remotes.sh once!

list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-player" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "pop-launcher" "xdg-desktop-portal-cosmic")

for item in "${list[@]}"
do
    echo "Processing: $item"
    # Standard stuff
    git submodule set-url rpms/$item https://src.fedoraproject.org/forks/ryanabx/rpms/$item.git
    git submodule set-branch -b rawhide rpms/$item
    # Add remotes
    cd rpms/$item
    git remote add upstream https://src.fedoraproject.org/rpms/$item.git
    git fetch upstream
    git remote add origin-ssh ssh://ryanabx@pkgs.fedoraproject.org/rpms/$item.git
    git fetch origin-ssh || true
    cd ../..
done
