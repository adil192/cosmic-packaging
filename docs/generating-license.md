# Generating Licenses

## Using the license_generator program

```cargo run -- license-for-spec <WORKING_DIRECTORY>```
```cargo run -- license-gpl <WORKING_DIRECTORY>```
```cargo run -- license-summary <WORKING_DIRECTORY>```

You will get an output in `<WORKING_DIRECTORY>/cosmic_licenses.txt`

## Checking licenses of rust projects in general:

```shell
cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{p}: {l}"
```

Thanks to Fabio Valentini for that command ^

Getting licenses for the `License:` section in the spec file:

```shell
cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{l}" | sort | uniq | sed '/OR/ s/.*/(&)/' | awk '{printf("%s AND ", $0)} END {print ""}' | sed 's/AND$//'
```

> **NOTE:** There might be an AND before and after, make sure to remove those!