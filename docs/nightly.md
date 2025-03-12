# Nightly Fedora COSMIC Builds

The nightly Fedora COSMIC builds are hosted on the [ryanabx/cosmic-epoch COPR](https://copr.fedorainfracloud.org/coprs/ryanabx/cosmic-epoch)


## How are the nightly packages built

Each package in the copr runs the `bootstrap.sh` script, which in turn calls the `cosmic-packaging-bootstrap.py` script, which prepares the sources for the srpm. From there, copr takes over and builds the resulting srpm.