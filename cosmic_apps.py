GPL3 = "GPL-3.0"
MPL2 = "MPL-2.0"
CC = "CC-BY-SA-4.0"

ROOTDIR = f"%{{buildroot}}"
BUILD_TARGET = f"target/release/"

def install_(path_from, path_to, perms):
    return f"""install -Dm{perms} {path_from} {ROOTDIR}/{path_to}"""

def contains_(path):
    return f"""{path}"""

def install_app(bin_name, appid, add_bin, add_desktop, add_scaled, add_symbolic, add_metainfo, prescriptor, resdir):
    res = """"""
    if add_bin:
        res += install_(f"target/release/{bin_name}", f"%{{_bindir}}/{bin_name}", "0755") + "\n"
    if add_desktop:
        res += install_(f"{prescriptor}{resdir}/{appid}.desktop", f"%{{_datadir}}/applications/{appid}.desktop", "0644") + "\n"
    if add_scaled:
        res += install_(f"{prescriptor}{resdir}/icons/{appid}.svg", f"%{{_datadir}}/icons/hicolor/scalable/apps/{appid}.svg", "0644") + "\n"
    if add_symbolic:
        res += install_(f"{prescriptor}{resdir}/icons/{appid}-symbolic.svg", f"%{{_datadir}}/icons/hicolor/symbolic/apps/{appid}-symbolic.svg", "0644") + "\n" # TODO
    if add_metainfo:
        res += install_(f"{prescriptor}{resdir}/{appid}.metainfo.xml", f"%{{_metainfodir}}/{appid}.metainfo.xml", "0644") + "\n"
    return res



def contains_app(bin_name, appid, add_bin, add_desktop, add_scaled, add_symbolic, add_metainfo, prescriptor):
    res = """"""
    if add_bin:
        res += contains_(f"""%{{_bindir}}/{bin_name}\n""")
    if add_desktop:
        res += contains_(f"""%{{_datadir}}/applications/{appid}.desktop\n""")
    if add_scaled:
        res += contains_(f"""%{{_datadir}}/icons/hicolor/scalable/apps/{appid}.svg\n""")
    if add_symbolic:
        res += contains_(f"""%{{_datadir}}/icons/hicolor/symbolic/apps/{appid}-symbolic.svg\n""") # TODO
    if add_metainfo:
        res += contains_(f"""%{{_metainfodir}}/{appid}.metainfo.xml\n""")
    return res

STANDARD_SOURCES = f"""
Source:         %{{crate}}.tar.gz
Source:         vendor.tar
"""

STANDARD_REQUIRES = f"""
# For now, we require all deps for all of cosmic-epoch
Requires:       libseat
Requires:       pop-icon-theme
Requires:       greetd
Requires:       greetd-selinux
Requires:       cage
Requires:       mozilla-fira-mono-fonts
Requires:       mozilla-fira-sans-fonts
"""

RUST_PACKAGING_REQUIRES = f"""
BuildRequires: cargo-rpm-macros >= 26.1
"""

STANDARD_BUILDREQUIRES = f"""
# For now, we require all deps for all of cosmic-epoch
BuildRequires:  make
BuildRequires:  which
BuildRequires:  git-core
BuildRequires:  just
BuildRequires:  rustc
BuildRequires:  lld
BuildRequires:  cargo
BuildRequires:  glib2-devel
BuildRequires:  gtk3-devel
BuildRequires:  dbus-devel
BuildRequires:  wayland-devel
BuildRequires:  clang-devel
BuildRequires:  libxkbcommon-devel
BuildRequires:  mesa-libgbm-devel
BuildRequires:  rust-rav1e+nasm-rs-devel
BuildRequires:  libappstream-glib
BuildRequires:  pipewire-devel
BuildRequires:  libglvnd-devel
BuildRequires:  libseat-devel
BuildRequires:  libinput-devel
BuildRequires:  pam-devel
BuildRequires:  flatpak-devel
"""

OLDSTANDARD_PREP = f"""
%autosetup -n %{{crate}} -p1 -a1
ls -a
mkdir -p .cargo
cp .vendor/config.toml .cargo/config.toml
"""

STANDARD_PREP = f"""
%autosetup -n %{{crate}} -p1
mv %{{_sourcedir}}/vendor.tar vendor.tar
ls -a
mkdir -p .cargo
cp .vendor/config.toml .cargo/config.toml
"""

STANDARD_BUILD_RUST_PACKAGING = f"""
%{{cargo_license_summary}}
%{{cargo_license}} > LICENSE.dependencies
%{{cargo_vendor_manifest}}
"""

STANDARD_FILES = f""""""

STANDARD_FILES_RUST_PACKAGING = f"""
%license LICENSE.md
%license LICENSE.dependencies
%license cargo-vendor.txt
%doc README.md
"""

STANDARD_GLOBALS_RUST_PACKAGING = f"""
%bcond_without check
%global __cargo_is_lib() 0
"""


COSMIC_APP_LIBRARY = {
"globals": "",
"name": "cosmic-app-library",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-applibrary",
"reposhort": "cosmic-applibrary",
"commit": "latest",
"summary": "A boilerplate template to get started with GTK, Rust, Meson, Flatpak, Debian made for Cosmic.",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-app-library","com.system76.CosmicAppLibrary",True, True, True, False, True, "")}
""",
}

COSMIC_APPLETS = {
"globals": f"%define debug_package %{{nil}}",
"name": "cosmic-applets",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-applets",
"reposhort": "cosmic-applets",
"commit": "latest",
"summary": "WIP applets for cosmic-panel",
"license": GPL3,
"sources": STANDARD_SOURCES + "\nPatch1: better_compile.patch",
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"""
just build-vendored
""",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
%{{_bindir}}/cosmic-applets
%{{_bindir}}/cosmic-panel-button
%{{_bindir}}/cosmic-app-list
%{{_bindir}}/cosmic-applet-audio
%{{_bindir}}/cosmic-applet-battery
%{{_bindir}}/cosmic-applet-bluetooth
%{{_bindir}}/cosmic-applet-minimize
%{{_bindir}}/cosmic-applet-network
%{{_bindir}}/cosmic-applet-notifications
%{{_bindir}}/cosmic-applet-power
%{{_bindir}}/cosmic-applet-status-area
%{{_bindir}}/cosmic-applet-tiling
%{{_bindir}}/cosmic-applet-time
%{{_bindir}}/cosmic-applet-workspaces
%{{_datadir}}/applications/com.system76.CosmicAppList.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletAudio.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletBattery.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletBluetooth.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletMinimize.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletNetwork.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletNotifications.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletPower.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletStatusArea.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletTiling.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletTime.desktop
%{{_datadir}}/applications/com.system76.CosmicAppletWorkspaces.desktop
%{{_datadir}}/applications/com.system76.CosmicPanelAppButton.desktop
%{{_datadir}}/applications/com.system76.CosmicPanelWorkspacesButton.desktop
%{{_datadir}}/cosmic/com.system76.CosmicAppList/v1/favorites
%{{_datadir}}/cosmic/com.system76.CosmicAppList/v1/filter_top_levels
%{{_datadir}}/icons/hicolor/scalable/app/com.system76.CosmicAppletStatusArea.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppList.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletAudio.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletBattery.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletBluetooth.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletMinimize.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletNetwork.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletNotifications.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletPower.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletTiling.Off.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletTiling.On.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletTime.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicAppletWorkspaces.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicPanelAppButton.svg
%{{_datadir}}/icons/hicolor/scalable/apps/com.system76.CosmicPanelWorkspacesButton.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-display-brightness-high-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-display-brightness-low-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-display-brightness-medium-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-display-brightness-off-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-0-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-0-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-0-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-0-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-10-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-10-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-10-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-10-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-100-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-100-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-20-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-20-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-20-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-20-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-35-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-35-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-35-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-35-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-5-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-5-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-5-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-5-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-50-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-50-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-50-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-50-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-65-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-65-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-65-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-65-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-80-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-80-limited-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-80-limited-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-80-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-90-charging-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-battery-level-90-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-bluetooth-active-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-bluetooth-disabled-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-notification-disabled-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-notification-new-symbolic.svg
%{{_datadir}}/icons/hicolor/scalable/status/cosmic-applet-notification-symbolic.svg
"""
}

COSMIC_BG = {
"globals": "",
"name": "cosmic-bg",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-bg",
"reposhort": "cosmic-bg",
"commit": "latest",
"summary": "COSMIC session service which applies backgrounds to displays",
"license": MPL2,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-bg","com.system76.CosmicBackground",True, True, True, True, True, "")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicBackground/*")}
""",
}

COSMIC_COMP = {
"globals": "",
"name": "cosmic-comp",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-comp",
"reposhort": "cosmic-comp",
"commit": "latest",
"summary": "Compositor for the COSMIC Desktop Environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"make all VENDOR=1",
"install": f"""
make install DESTDIR=%{{buildroot}} prefix=%{{_prefix}}
install -Dm0644 config.ron %{{buildroot}}/%{{_sysconfdir}}/cosmic-comp/config.ron
""",
"files": f"""
{contains_app("cosmic-comp","com.system76.CosmicComp",True, False, False, False, False, "")}
{contains_(f"%{{_sysconfdir}}/cosmic-comp/config.ron")}
""",
}

COSMIC_EDIT = {
"globals": "",
"name": "cosmic-edit",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-edit",
"reposhort": "cosmic-edit",
"commit": "latest",
"summary": "Text editor built using libcosmic for the COSMIC Desktop Environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-edit","com.system76.CosmicEdit",True, True, False, False, True, "")}
%{{_datadir}}/icons/hicolor/128x128/apps/com.system76.CosmicEdit.svg
%{{_datadir}}/icons/hicolor/16x16/apps/com.system76.CosmicEdit.svg
%{{_datadir}}/icons/hicolor/24x24/apps/com.system76.CosmicEdit.svg
%{{_datadir}}/icons/hicolor/256x256/apps/com.system76.CosmicEdit.svg
%{{_datadir}}/icons/hicolor/32x32/apps/com.system76.CosmicEdit.svg
%{{_datadir}}/icons/hicolor/48x48/apps/com.system76.CosmicEdit.svg
%{{_datadir}}/icons/hicolor/64x64/apps/com.system76.CosmicEdit.svg
""",
}

COSMIC_FILES = {
"globals": "",
"name": "cosmic-files",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-files",
"reposhort": "cosmic-files",
"commit": "latest",
"summary": "File browser built using libcosmic for the COSMIC Desktop Environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-files","com.system76.CosmicFiles",True, True, False, False, True, "")}
%{{_datadir}}/icons/hicolor/128x128/apps/com.system76.CosmicFiles.svg
%{{_datadir}}/icons/hicolor/16x16/apps/com.system76.CosmicFiles.svg
%{{_datadir}}/icons/hicolor/24x24/apps/com.system76.CosmicFiles.svg
%{{_datadir}}/icons/hicolor/256x256/apps/com.system76.CosmicFiles.svg
%{{_datadir}}/icons/hicolor/32x32/apps/com.system76.CosmicFiles.svg
%{{_datadir}}/icons/hicolor/48x48/apps/com.system76.CosmicFiles.svg
%{{_datadir}}/icons/hicolor/64x64/apps/com.system76.CosmicFiles.svg
""",
}

COSMIC_GREETER = {
"globals": "",
"name": "cosmic-greeter",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-greeter",
"reposhort": "cosmic-greeter",
"commit": "latest",
"summary": "Libcosmic greeter for greetd, which can be run inside cosmic-comp",
"license": GPL3,
"sources": STANDARD_SOURCES + "\nPatch1: service.patch",
"buildrequires": STANDARD_BUILDREQUIRES + f"\nBuildRequires:   systemd-rpm-macros\n%{{?sysusers_requires_compat}}",
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"""
install -Dm0755 {BUILD_TARGET}/cosmic-greeter %{{buildroot}}/%{{_bindir}}/cosmic-greeter
install -Dm0755 {BUILD_TARGET}/cosmic-greeter-daemon %{{buildroot}}/%{{_bindir}}/cosmic-greeter-daemon
install -Dm0644 dbus/com.system76.CosmicGreeter.conf %{{buildroot}}/%{{_datadir}}/dbus-1/system.d/com.system76.CosmicGreeter.conf
install -Dm0644 debian/cosmic-greeter.sysusers %{{buildroot}}/%{{_sysusersdir}}/cosmic-greeter.conf
install -Dm0644 debian/cosmic-greeter.tmpfiles %{{buildroot}}/%{{_tmpfilesdir}}/cosmic-greeter.conf
install -Dm0644 cosmic-greeter.toml %{{buildroot}}/%{{_prefix}}/etc/greetd/cosmic-greeter.toml
install -Dm0644 debian/cosmic-greeter.service %{{buildroot}}/%{{_unitdir}}/cosmic-greeter.service
install -Dm0644 debian/cosmic-greeter-daemon.service %{{buildroot}}/%{{_unitdir}}/cosmic-greeter-daemon.service

%pre
%sysusers_create_compat debian/cosmic-greeter.sysusers

%post
%systemd_post cosmic-greeter.service
%systemd_post cosmic-greeter-daemon.service

%preun
%systemd_preun cosmic-greeter.service
%systemd_preun cosmic-greeter-daemon.service

%postun
%systemd_postun cosmic-greeter.service
%systemd_postun cosmic-greeter-daemon.service
""",
"files": f"""
%{{_bindir}}/cosmic-greeter
%{{_bindir}}/cosmic-greeter-daemon
%{{_datadir}}/dbus-1/system.d/com.system76.CosmicGreeter.conf
%{{_sysusersdir}}/cosmic-greeter.conf
%{{_tmpfilesdir}}/cosmic-greeter.conf
%{{_prefix}}/etc/greetd/cosmic-greeter.toml
%{{_unitdir}}/cosmic-greeter.service
%{{_unitdir}}/cosmic-greeter-daemon.service
""",
}

COSMIC_ICONS = {
"globals": f"%define debug_package %{{nil}}",
"name": "cosmic-icons",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-icons",
"reposhort": "cosmic-icons",
"commit": "latest",
"summary": "System76 Cosmic icon theme for Linux",
"license": CC,
"sources": f"Source:         %{{crate}}.tar.gz",
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": f"%autosetup -n cosmic-icons",
"build": f"echo done",
"install": f"just rootdir=%{{buildroot}} install",
"files": f"""
{contains_(f"%{{_datadir}}/icons/Cosmic/scalable/*")}
{contains_(f"%{{_datadir}}/icons/Cosmic/index.theme")}
""",
}

COSMIC_LAUNCHER = {
"globals": "",
"name": "cosmic-launcher",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-launcher",
"reposhort": "cosmic-launcher",
"commit": "latest",
"summary": "Layer shell frontend for Pop Launcher",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-launcher","com.system76.CosmicLauncher",True, True, True, False, True, "")}
""",
}

COSMIC_NOTIFICATIONS = {
"globals": "",
"name": "cosmic-notifications",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-notifications",
"reposhort": "cosmic-notifications",
"commit": "latest",
"summary": "Layer Shell notifications daemon which integrates with COSMIC",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-notifications","com.system76.CosmicNotifications",True, True, True, False, True, "")}
""",
}

COSMIC_OSD = {
"globals": "",
"name": "cosmic-osd",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-osd",
"reposhort": "cosmic-osd",
"commit": "latest",
"summary": "OSDs for the COSMIC desktop environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"make all VENDOR=1",
"install": f"make install DESTDIR=%{{buildroot}} prefix=%{{_prefix}}",
"files": f"""
{contains_app("cosmic-osd","com.system76.CosmicOsd",True, False, False, False, False, "")}
""",
}

COSMIC_PANEL = {
"globals": "",
"name": "cosmic-panel",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-panel",
"reposhort": "cosmic-panel",
"commit": "latest",
"summary": "Panel for COSMIC Desktop Environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-panel","com.system76.CosmicPanel",True, False, False, False, False, "")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicPanel.Dock/*")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicPanel.Panel/*")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicPanel/*")}
""",
}

COSMIC_PLAYER = {
"globals": "",
"name": "cosmic-player",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-player",
"reposhort": "cosmic-player",
"commit": "latest",
"summary": "WIP COSMIC media player",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-files","com.system76.CosmicFiles",True, True, False, False, False, "")}
""",
}

COSMIC_RANDR = {
"globals": "",
"name": "cosmic-randr",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-randr",
"reposhort": "cosmic-randr",
"commit": "latest",
"summary": "Library and utility for displaying and configuring Wayland outputs",
"license": MPL2,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-randr","",True, False, False, False, False, "")}
""",
}

COSMIC_SCREENSHOT = {
"globals": "",
"name": "cosmic-screenshot",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-screenshot",
"reposhort": "cosmic-screenshot",
"commit": "latest",
"summary": "Utility for capturing screenshots via XDG Desktop Portal",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-screenshot","com.system76.CosmicScreenshot",True, True, False, False, False, "")}
""",
}

COSMIC_SESSION = {
"globals": "",
"name": "cosmic-session",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-session",
"reposhort": "cosmic-session",
"commit": "latest",
"summary": "Session manager for the COSMIC desktop environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES + "\nBuildRequires: systemd-rpm-macros",
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just vendor=1 all",
"install": f"just rootdir=%{{buildroot}} install",
"files": f"""
{contains_app("cosmic-session","",True, False, False, False, False, "")}
{contains_(f"%{{_bindir}}/start-cosmic")}
{contains_(f"%{{_userunitdir}}/cosmic-session.target")}
{contains_(f"%{{_datadir}}/wayland-sessions/cosmic.desktop")}
{contains_(f"%{{_datadir}}/applications/cosmic-mimeapps.list")}
""",
}

COSMIC_SETTINGS_DAEMON = {
"globals": "",
"name": "cosmic-settings-daemon",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-settings-daemon",
"reposhort": "cosmic-settings-daemon",
"commit": "latest",
"summary": "Settings daemon for cosmic-settings",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"make all VENDOR=1",
"install": f"make install DESTDIR=%{{buildroot}} prefix=%{{_prefix}}",
"files": f"""
{contains_app("cosmic-settings-daemon","",True, False, False, False, False, "")}
""",
}

COSMIC_SETTINGS = {
"globals": f"%define debug_package %{{nil}}",
"name": "cosmic-settings",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-settings",
"reposhort": "cosmic-settings",
"commit": "latest",
"summary": "The settings application for the COSMIC desktop environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} install",
"files": f"""
{contains_app("cosmic-settings","com.system76.CosmicSettings",True, True, False, False, False, "")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicTheme.Dark.Builder/v1/*")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicTheme.Dark/v1/*")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicTheme.Light.Builder/v1/*")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicTheme.Light/v1/*")}
{contains_(f"%{{_datadir}}/cosmic/com.system76.CosmicTheme.Mode/v1/*")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-dark-style-round.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-dark-style-slightly-round.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-dark-style-square.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-light-style-round.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-light-style-slightly-round.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-light-style-square.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-mode-dark.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/status/illustration-appearance-mode-light.svg")}
""",
}

COSMIC_STORE = {
"globals": "",
"name": "cosmic-store",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-store",
"reposhort": "cosmic-store",
"commit": "latest",
"summary": "COSMIC App Store",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-store","com.system76.CosmicStore",True, True, False, False, False, "")}
""",
}

COSMIC_TERM = {
"globals": "",
"name": "cosmic-term",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-term",
"reposhort": "cosmic-term",
"commit": "latest",
"summary": "WIP COSMIC terminal emulator, built using alacritty_terminal that is provided by the alacritty project. cosmic-term provides bidirectional rendering and ligatures with a custom renderer based on cosmic-text.",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} prefix=%{{_prefix}} install",
"files": f"""
{contains_app("cosmic-term","com.system76.CosmicTerm",True, True, False, False, True, "")}
%{{_datadir}}/icons/hicolor/128x128/apps/com.system76.CosmicTerm.svg
%{{_datadir}}/icons/hicolor/16x16/apps/com.system76.CosmicTerm.svg
%{{_datadir}}/icons/hicolor/24x24/apps/com.system76.CosmicTerm.svg
%{{_datadir}}/icons/hicolor/256x256/apps/com.system76.CosmicTerm.svg
%{{_datadir}}/icons/hicolor/32x32/apps/com.system76.CosmicTerm.svg
%{{_datadir}}/icons/hicolor/48x48/apps/com.system76.CosmicTerm.svg
%{{_datadir}}/icons/hicolor/64x64/apps/com.system76.CosmicTerm.svg
""",
}

COSMIC_WORKSPACES = {
"globals": "",
"name": "cosmic-workspaces",
"version": "0.1.0",
"repo": "https://github.com/pop-os/cosmic-workspaces-epoch",
"reposhort": "cosmic-workspaces-epoch",
"commit": "latest",
"summary": "COSMIC Workspaces",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"make all VENDOR=1",
"install": f"make install DESTDIR=%{{buildroot}} prefix=%{{_prefix}}",
"files": f"""
{contains_app("cosmic-workspaces","com.system76.CosmicWorkspaces",True, True, True, False, False, "")}
""",
}

COSMIC_XDG_DESKTOP_PORTAL = {
"globals": "",
"name": "xdg-desktop-portal-cosmic",
"version": "0.1.0",
"repo": "https://github.com/pop-os/xdg-desktop-portal-cosmic",
"reposhort": "xdg-desktop-portal-cosmic",
"commit": "latest",
"summary": "XDG Desktop Portals for the COSMIC Desktop Environment",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"make all VENDOR=1",
"install": f"make install DESTDIR=%{{buildroot}} prefix=%{{_prefix}}",
"files": f"""
{contains_(f"%{{_libexecdir}}/xdg-desktop-portal-cosmic")}
{contains_(f"%{{_datadir}}/dbus-1/services/org.freedesktop.impl.portal.desktop.cosmic.service")}
{contains_(f"%{{_datadir}}/xdg-desktop-portal/portals/cosmic.portal")}
{contains_(f"%{{_datadir}}/xdg-desktop-portal/cosmic-portals.conf")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/actions/screenshot-screen-symbolic.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/actions/screenshot-selection-symbolic.svg")}
{contains_(f"%{{_datadir}}/icons/hicolor/scalable/actions/screenshot-window-symbolic.svg")}
""",
}

POP_LAUNCHER = {
"globals": "",
"name": "pop-launcher",
"version": "0.1.0",
"repo": "https://github.com/pop-os/launcher",
"reposhort": "launcher",
"commit": "latest",
"summary": "Modular IPC-based desktop launcher service ",
"license": GPL3,
"sources": STANDARD_SOURCES + f"\nPatch1: install.patch",
"buildrequires": STANDARD_BUILDREQUIRES,
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP,
"build": f"just build-vendored",
"install": f"just rootdir=%{{buildroot}} install",
"files": f"""
{contains_(f"%{{_bindir}}/pop-launcher")}
{contains_(f"%{{_prefix}}/lib/pop-launcher/*")}
""",
}

SYSTEM76_POWER = {
"globals": f"%define debug_package %{{nil}}",
"name": "system76-power",
"version": "1.1.25",
"repo": "https://github.com/pop-os/system76-power",
"reposhort": "system76-power",
"commit": "latest",
"summary": "System76 Power Management",
"license": GPL3,
"sources": STANDARD_SOURCES,
"buildrequires": STANDARD_BUILDREQUIRES + "\nBuildRequires: rust-hidapi+linux-shared-libusb-devel\nBuildRequires: libusb1-devel\nBuildRequires: systemd-rpm-macros",
"requires": STANDARD_REQUIRES,
"prep": STANDARD_PREP + f"\ntar -pxf vendor.tar",
"build": f"""cargo build --release --offline --frozen""",
"install": f"""make install DESTDIR=%{{buildroot}} prefix=%{{_prefix}}""",
"files": f"""
%{{_bindir}}/system76-power
%{{_unitdir}}/com.system76.PowerDaemon.service
%{{_datadir}}/dbus-1/interfaces/com.system76.PowerDaemon.xml
%{{_datadir}}/dbus-1/system.d/com.system76.PowerDaemon.conf
%{{_datadir}}/polkit-1/actions/com.system76.PowerDaemon.policy
"""
}