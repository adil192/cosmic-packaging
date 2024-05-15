```sh
fedpkg request-repo ...
fedpkg clone <package> && cd <package>
fedpkg import /path/to/package.src.rpm
fedpkg commit -m "Initial import to Fedora (rhbz#XXXXXXXX)"
fedpkg push && fedpkg build
```

```
fkinit
```