#!/bin/bash

# Define a list of strings
# list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-osd" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-notifications" "cosmic-panel" "cosmic-randr" "cosmic-screenshot" "cosmic-workspaces" "xdg-desktop-portal-cosmic")
# list=("cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-osd" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-notifications" "cosmic-panel" "cosmic-randr" "cosmic-screenshot" "cosmic-workspaces" "xdg-desktop-portal-cosmic")
list=("cosmic-session")

# Loop through the list
for item in "${list[@]}"
do
    # Run a command for each string
    echo "Processing: $item"
    cargo run -- setup-build ~/workdir $item --build-branch f41 --source-branch rawhide
done
