# Generated using the scripts at https://pagure.io/fedora-cosmic/cosmic-packaging/blob/main/f/scripts

%global commit ###
%global shortcommit %{sub %{commit} 1 7}
%global commitdatestring ###
%global commitdate ###
%global cosmic_minver ###

Name:           cosmic-wallpapers
Version: ###
Release:        2
Summary:        Default wallpapers for the COSMIC Desktop Environment

# All cosmic wallpapers are either public domain or CC-BY-SA-4.0
License:        CC-BY-SA-4.0

URL:            https://github.com/pop-os/cosmic-wallpapers

Source0:        https://github.com/pop-os/cosmic-wallpapers/archive/%{commit}/cosmic-wallpapers-%{shortcommit}.tar.gz

# https://github.com/pop-os/cosmic-wallpapers/pull/7
Patch0:         https://patch-diff.githubusercontent.com/raw/pop-os/cosmic-wallpapers/pull/7.patch

BuildArch:      noarch

BuildRequires:  make

%global _description %{expand:
%{summary}.}

%description %{_description}

%prep
%autosetup -n cosmic-wallpapers-%{commit} -p1

%build

%install
# Set vergen environment variables
export VERGEN_GIT_COMMIT_DATE="date --utc '%{commitdatestring}'"
export VERGEN_GIT_SHA="%{commit}"
make install DESTDIR=%{buildroot} prefix=%{_prefix}

%files
%dir %{_datadir}/backgrounds/cosmic
%{_datadir}/backgrounds/cosmic/*
%license LICENSE

%changelog
%autochangelog
    
