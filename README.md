# cosmic-packaging

WIP Packaging for the COSMIC desktop environment

Testing for this packaging may be done at this [COPR](https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch/)

Be sure to report issues with the packaging in this repo. Report COSMIC related issues in [their repo](https://github.com/pop-os/cosmic-epoch/issues) If unsure whether an issue is with packaging or COSMIC itself, start here, in this repo.

# Documentation

To build the documentation, install `mdbook` and build the `docs` folder:

```shell
cargo install mdbook
mdbook build docs
```

You can also serve a live webserver for the docs with `mdbook serve docs`