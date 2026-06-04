# Possible packages to build
PACKAGES: dict[str, str] = {
    "cosmic-app-library": "cosmic-applibrary",
    "cosmic-applets": "cosmic-applets",
    "cosmic-bg": "cosmic-bg",
    "cosmic-comp": "cosmic-comp",
    "cosmic-edit": "cosmic-edit",
    "cosmic-files": "cosmic-files",
    "cosmic-greeter": "cosmic-greeter",
    "cosmic-icon-theme": "cosmic-icons",
    "cosmic-idle": "cosmic-idle",
    "cosmic-initial-setup": "cosmic-initial-setup",
    "cosmic-launcher": "cosmic-launcher",
    "cosmic-notifications": "cosmic-notifications",
    "cosmic-osd": "cosmic-osd",
    "cosmic-panel": "cosmic-panel",
    "cosmic-player": "cosmic-player",
    "cosmic-randr": "cosmic-randr",
    "cosmic-screenshot": "cosmic-screenshot",
    "cosmic-session": "cosmic-session",
    "cosmic-settings": "cosmic-settings",
    "cosmic-settings-daemon": "cosmic-settings-daemon",
    "cosmic-store": "cosmic-store",
    "cosmic-term": "cosmic-term",
    "cosmic-wallpapers": "cosmic-wallpapers",
    "cosmic-workspaces": "cosmic-workspaces-epoch",
    "xdg-desktop-portal-cosmic": "xdg-desktop-portal-cosmic",
    "pop-launcher": "launcher",
}

# Possible versions
FEDORA_BRANCHES = ["rawhide", "f44", "f43"]  # 42 is now EOL
SIDE_TAG_BRANCHES = ["rawhide"]
RAWHIDE_NUMBER = "45"
RAWHIDE_BRANCH = f"f{RAWHIDE_NUMBER}"
