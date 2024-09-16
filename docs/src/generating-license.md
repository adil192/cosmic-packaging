# Generating Licenses

Checking licenses of rust projects:

```shell
cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{p}: {l}"
```

Thanks to Fabio Valentini for that command ^

Getting licenses for the `License:` section in the spec file:

```shell
cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{l}" | sort | uniq | sed '/OR/ s/.*/(&)/' | awk '{printf("%s AND ", $0)} END {print ""}' | sed 's/AND$//'
```

> **NOTE:** There might be an AND before and after, make sure to remove those!


Licenses updated so far:

cosmic-bg
cosmic-comp