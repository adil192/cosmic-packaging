# Generated using the scripts at https://pagure.io/fedora-cosmic/cosmic-packaging/blob/main/f/scripts

%global commit ###
%global shortcommit %{sub %{commit} 1 7}
%global commitdatestring ###
%global commitdate ###
%global cosmic_minver ###

Name:           cosmic-wallpapers
Version: ###
Release:        %autorelease
Summary:        Default wallpapers for the COSMIC Desktop Environment

# All cosmic wallpapers are either public domain or CC-BY-SA-4.0
License:        CC-BY-SA-4.0

URL:            https://github.com/pop-os/cosmic-wallpapers

# How to recreate this source
# Install git-lfs
# Clone https://github.com/pop-os/cosmic-wallpapers
# Checkout commit %{commit}
# dnf install git-lfs
# git clone https://github.com/pop-os/cosmic-wallpapers
# cd cosmic-wallpapers && git checkout %{commit} && cd ..
# tar -pczf cosmic-wallpapers-archive-%{shortcommit}.tar.gz cosmic-wallpapers
Source0:        cosmic-wallpapers-archive-%{shortcommit}.tar.gz

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
    
