# Bazel Dependency File Conversion

Convert a Bazel dependency file to a `fossa-deps.yml`.

### Compatibility
- Works for `deps.bzl` that is generated from [bazel-gazelle](https://github.com/bazelbuild/bazel-gazelle) or similar.
Please see the example `deps.bzl` in this directory.

### What does it do?
When you run `python fossa-deps-converter.py`, which should be ran where `deps.bzl` exists in the same directory, it looks for `go_repository` blocks
and extracts the name of the dependency and its version. It finds the version by inspecting whether
`commit`, `tag` or `version` exists in the `go` dependency block. At the moment, we assume these are `referenced-dependencies` and are direct dependencies of the project.
See our `fossa-deps` [documentation](https://github.com/fossas/fossa-cli/blob/master/docs/references/files/fossa-deps.md#referenced-dependencies) for more details.

### What does it output?
It outputs a compatible `fossa-deps.yml`.

### How do you analyse only the `fossa-deps.yml` file?

There are two ways to do this:

#### Run analysis with the `--exclude-path` flag

Simply run `fossa analyze --exclude-path .`, provided that `FOSSA_API_KEY` is set (either using the flag or is set as an env variable) and the `fossa-deps` file exists.

#### Exclude all paths via `.fossa.yml`

Exclude the root of the directory via `paths.exclude`:

```yaml
version: 3

paths:
  exclude:
    - ./
```

Please see our [documentation](https://github.com/fossas/fossa-cli/blob/master/docs/references/files/fossa-yml.md) for more details.
