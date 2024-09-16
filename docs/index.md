# COSMIC Packaging for Fedora

The current state of packaging is pretty set, each individual rpm and their patches can be found in the `rpms/*` folder.

The `scripts` folder contains scripts used in the unofficial working repo for the COSMIC master branch <https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch/>. These can be applied to any copr though, provided you set it up properly.


Checking licenses of rust projects:

```shell
cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{p}: {l}"
```

Thanks to Fabio Valentini for that command ^