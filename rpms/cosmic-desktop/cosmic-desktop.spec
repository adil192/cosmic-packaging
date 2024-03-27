%global ver ###
%global commit ###
%global date ###

Name:           cosmic-desktop
Version:        %{ver}~%{date}
Release:        %autorelease
Summary:        The next generation COSMIC Desktop Environment

License:        GPL-3.0

URL:            https://github.com/pop-os/cosmic-epoch

Requires:       cosmic-app-library
Requires:       cosmic-applets
Requires:       cosmic-bg
Requires:       cosmic-comp
Requires:       cosmic-icons
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
Recommends:     cosmic-files
Recommends:     cosmic-greeter
Recommends:     cosmic-store
Recommends:     cosmic-term
Recommends:     system76-power

%global _description %{expand:
%{summary}.}

%description %{_description}

%prep

%build

%install

%files

%changelog
%autochangelog
