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


To build (1.0.0~alpha.3 2024-09-28):

> **TODO:** Build these, but first I have to wait on the ssh key to refresh 

- ~~cosmic-app-library~~
- ~~cosmic-applets~~
- ~~cosmic-bg~~
- ~~cosmic-comp~~
- ~~cosmic-edit~~
- ~~cosmic-files~~
- ~~cosmic-greeter~~
- ~~cosmic-icon-theme~~
- ~~cosmic-osd~~
- ~~cosmic-settings~~
- ~~cosmic-settings-daemon~~
- ~~cosmic-store~~
- ~~cosmic-notifications~~
- ~~cosmic-panel~~
- ~~cosmic-randr~~
- ~~cosmic-screenshot~~
- ~~cosmic-workspaces~~
- ~~xdg-desktop-portal-cosmic~~
- ~~cosmic-launcher~~
- ~~cosmic-session~~
- ~~cosmic-term~~
- ~~pop-launcher~~


Make sure wget is installed!

```shell
cargo run -- setup-build ~/workdir <PACKAGE_NAME> --srpm-url <SRPM_URL> --version 1.0.0~alpha.5.1
``` 