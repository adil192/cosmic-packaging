#!/bin/bash

list=("cosmic-app-library" "cosmic-applets" "cosmic-bg" "cosmic-comp" "cosmic-edit" "cosmic-files" "cosmic-greeter" "cosmic-icon-theme" "cosmic-idle" "cosmic-launcher" "cosmic-notifications" "cosmic-osd" "cosmic-panel" "cosmic-player" "cosmic-randr" "cosmic-screenshot" "cosmic-session" "cosmic-settings" "cosmic-settings-daemon" "cosmic-store" "cosmic-term" "cosmic-wallpapers" "cosmic-workspaces" "pop-launcher" "xdg-desktop-portal-cosmic")

echo "WARNING: This will erase everything in ~/workdir. Are you sure about this?"
read v

MAX_JOBS=5

function build_package() {
    pkg=$1
    echo "======================================"
    echo "Processing package $pkg..."
    rm -rf ~/workdir/$pkg && mkdir -p ~/workdir/$pkg
    if cargo run -- setup-build ~/workdir $pkg --auto-srpm --version 1.0.0~beta.6 > /dev/null 2>&1; then
        echo "rawhide $pkg success"
        rm -rf ~/workdir/$pkg && mkdir -p ~/workdir/$pkg
        cargo run -- setup-build ~/workdir $pkg --build-branch f42 --source-branch rawhide > /dev/null 2>&1 && echo "f42 $pkg success" || echo "f42 $pkg failure"
        rm -rf ~/workdir/$pkg && mkdir -p ~/workdir/$pkg
        cargo run -- setup-build ~/workdir $pkg --build-branch f41 --source-branch rawhide > /dev/null 2>&1 && echo "f41 $pkg success" || echo "f41 $pkg failure"
    else
        echo "WARNING: rawhide $pkg failure. REDO THIS ONE"
    fi
    echo "======================================"
}


for item in "${list[@]}"
do
    
    build_package $item &
    ((count++))

    if (( count % MAX_JOBS == 0 )); then
        wait
    fi
done

wait 
