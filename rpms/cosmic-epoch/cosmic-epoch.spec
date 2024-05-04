%global ver ###
%global commit ###
%global date ###

Name:           cosmic-epoch
Version:        %{ver}~git%{date}.%{sub %{commit} 1 7}
Release:        %autorelease
Summary:        The next generation COSMIC Desktop Environment

License:        GPL-3.0

URL:            https://github.com/pop-os/cosmic-epoch

Requires:       cosmic-desktop

%global _description %{expand:
%{summary}.}

%description %{_description}

%prep

%build

%install

%files

%changelog
%autochangelog
