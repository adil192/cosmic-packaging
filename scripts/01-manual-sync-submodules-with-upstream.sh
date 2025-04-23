#!/bin/bash

# Run this from the root of the cosmic-packaging repo!
# If you haven't ran 00-manual-setup-submodule-remotes.sh, go ahead and do so!
# You only need to run 00-manual-setup-submodule.remotes.sh once!

list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-player" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "pop-launcher" "xdg-desktop-portal-cosmic")

for item in "${list[@]}"
do
    echo "Processing: $item"
    cd rpms/$item
    git fetch origin
    git fetch origin-ssh
    git fetch upstream
    git pull origin
    read -p "If pulling failed, make adjustments and press enter to continue!"
    git rebase upstream/rawhide
    read -p "Make adjustments as needed and press enter to continue!"
    git push --force origin HEAD:rawhide
    cd ../..
done

