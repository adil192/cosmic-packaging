Name:           cosmic-desktop
Version: 1.0.0~beta.7
Release:        %autorelease
Summary:        The next generation COSMIC Desktop Environment, in a package group!

License:        GPL-3.0

URL:            https://github.com/pop-os/cosmic-epoch

BuildArch:      noarch

Requires:       cosmic-app-library
Requires:       cosmic-applets
Requires:       cosmic-bg
Requires:       cosmic-comp
Requires:       cosmic-edit
Requires:       cosmic-files
Requires:       cosmic-greeter
Requires:       cosmic-icon-theme
Requires:       cosmic-idle
Requires:       cosmic-initial-setup
Requires:       cosmic-launcher
Requires:       cosmic-notifications
Requires:       cosmic-osd
Requires:       cosmic-panel
Requires:       cosmic-player
Requires:       cosmic-randr
Requires:       cosmic-screenshot
Requires:       cosmic-session
Requires:       cosmic-settings
Requires:       cosmic-settings-daemon
Requires:       cosmic-store
Requires:       cosmic-term
Requires:       cosmic-wallpapers
Requires:       cosmic-workspaces
Requires:       pop-launcher
Requires:       xdg-desktop-portal-cosmic


%global _description %{expand:
%{summary}.}

%description %{_description}

%prep

%build

%install

%files

%changelog
%autochangelog
