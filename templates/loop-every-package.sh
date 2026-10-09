#!/bin/sh
# Template to perform an action per package

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
    "cosmic-monitor"
    "cosmic-notifications"
    "cosmic-osd"
    "cosmic-osk"
    "cosmic-panel"
    "cosmic-player"
    "cosmic-randr"
    "cosmic-screenshot"
    "cosmic-session"
    "cosmic-settings"
    "cosmic-settings-daemon"
    "cosmic-store"
    "cosmic-term"
    "cosmic-viewer"
    "cosmic-wallpapers"
    "cosmic-workspaces"
    "pop-launcher"
    "xdg-desktop-portal-cosmic"
    )

function perform_package_action() {
    pkg=$1
    echo "$pkg"
    # Perform desired action here
}

for item in "${list[@]}"
do
    perform_package_action $item
done
