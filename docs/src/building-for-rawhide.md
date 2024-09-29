# Building for Rawhide

```sh
fedpkg request-repo <name> <bug>
fedpkg clone <package> && cd <package>
fedpkg import /path/to/package.src.rpm
fedpkg commit -m "Initial import to Fedora (rhbz#XXXXXXXX)"
fedpkg push && fedpkg build
```

```
fkinit
```


To build (1.0.0~alpha.2 2024-09-28):

> **TODO:** Build these, but first I have to wait on the ssh key to refresh 

- ~~cosmic-comp~~
- ~~cosmic-icon-theme~~
- ~~cosmic-app-library~~
- ~~xdg-desktop-portal-cosmic~~
- ~~cosmic-edit~~
- ~~cosmic-files~~
- ~~cosmic-randr~~
- ~~cosmic-settings~~
- ~~cosmic-settings-daemon~~
- ~~cosmic-greeter~~
- ~~cosmic-osd~~
- ~~cosmic-store~~
- ~~cosmic-workspaces~~
- ~~cosmic-screenshot~~
- ~~cosmic-panel~~


- cosmic-app-library
- cosmic-comp
- cosmic-edit
- cosmic-files
- cosmic-greeter
- cosmic-icon-theme
- cosmic-osd
- cosmic-panel
- cosmic-randr
- cosmic-screenshot
- cosmic-settings
- cosmic-settings-daemon
- cosmic-store
- cosmic-workspaces
- xdg-desktop-portal-cosmic

Missing:

- cosmic-applets
- cosmic-bg
- cosmic-launcher
- cosmic-notifications
- cosmic-session
- cosmic-term
- pop-launcher

```shell
cargo run -- setup-build ~/workdir <PACKAGE_NAME> <SRPM_URL> 1.0.0~alpha.2
``` 