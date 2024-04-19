%define debug_package %{nil}

%global ver ###
%global commit ###
%global date ###

Name:           cosmic-icons
Version:        %{ver}~git%{date}.%{sub %{commit} 1 7}
Release:        %autorelease
Summary:        Icon theme for the COSMIC Desktop Environment.

License:        CC-BY-SA-4.0

URL:            https://github.com/pop-os/cosmic-icons

# To create this source:
# * git clone the repository
# * tar -pcJf $name-$commit.tar.xz
Source:         cosmic-icons-%{commit}.tar.xz

BuildRequires:  just

Requires:       pop-icon-theme

%global _description %{expand:
%{summary}.}

%description %{_description}

%prep
%autosetup -n cosmic-icons-%{commit}

%build

%install
just rootdir=%{buildroot} install

%files
%{_datadir}/icons/Cosmic/scalable/*
%{_datadir}/icons/Cosmic/index.theme


%changelog
%autochangelog
    