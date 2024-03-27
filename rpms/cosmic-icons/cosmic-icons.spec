%define debug_package %{nil}

%global ver ###
%global commit ###
%global date ###

Name:           cosmic-icons
Version:        %{ver}~%{date}
Release:        %autorelease
Summary:        Icon theme for the COSMIC Desktop Environment.

SourceLicense:  CC-BY-SA-4.0
License:        GPL-3.0

URL:            https://github.com/pop-os/cosmic-icons
Source:         cosmic-icons-%{ver}.tar.xz

BuildRequires:  just

%global _description %{expand:
%{summary}.}

%description %{_description}

%prep
%autosetup -n cosmic-icons-%{ver}

%build

%install
just rootdir=%{buildroot} install

%files
%{_datadir}/icons/Cosmic/scalable/*
%{_datadir}/icons/Cosmic/index.theme


%changelog
%autochangelog
    