Name:           cosmic-desktop
Version: ###
Release:        %autorelease
Summary:        The next generation COSMIC Desktop Environment

License:        GPL-3.0

URL:            https://github.com/pop-os/cosmic-epoch

BuildArch:      noarch

Requires:       cosmic-app-library
Requires:       cosmic-applets
Requires:       cosmic-bg
Requires:       cosmic-comp
Requires:       cosmic-files
Requires:       cosmic-greeter
Requires:       cosmic-icon-theme >= %{cosmic_minver}
Requires:       cosmic-launcher
Requires:       cosmic-notifications
Requires:       cosmic-osd
Requires:       cosmic-panel
Requires:       cosmic-randr
Requires:       cosmic-screenshot
Requires:       cosmic-session
Requires:       cosmic-settings
Requires:       cosmic-settings-daemon
Requires:       cosmic-workspaces
Requires:       pop-launcher
Requires:       xdg-desktop-portal-cosmic

Recommends:     cosmic-edit
Recommends:     cosmic-player
Recommends:     cosmic-store
Recommends:     cosmic-term
Recommends:     cosmic-wallpapers

%global _description %{expand:
%{summary}.}

%description %{_description}

%prep

%build

%install

%files

%changelog
%autochangelog
