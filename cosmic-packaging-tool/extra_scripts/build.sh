#!/bin/bash

# Define a list of strings
# list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "xdg-desktop-portal-cosmic")
# list=("cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "xdg-desktop-portal-cosmic")

list=("cosmic-settings" "cosmic-settings-daemon")

# Loop through the list
for item in "${list[@]}"
do
    # Run a command for each string
    echo "Processing: $item"
    rm -rf ~/workdir && mkdir -p ~/workdir
    cargo run -- setup-build ~/workdir $item --auto-srpm --version 1.0.0~alpha.5
    rm -rf ~/workdir && mkdir -p ~/workdir
    cargo run -- setup-build ~/workdir $item --build-branch f41 --source-branch rawhide
done
