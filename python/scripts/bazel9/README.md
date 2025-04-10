# Generate FOSSA `fossa-deps.yaml` from Bazel `MODULE.bazel`

This script (`generate_fossa_deps.py`) reads your Bazel project's `MODULE.bazel` file and generates a `fossa-deps.yaml` file that is compatible with [FOSSA](https://fossa.com/)'s `remote-dependencies` format.

It fetches actual source archive URLs for each dependency using metadata from the [Bazel Central Registry](https://registry.bazel.build/), ensuring the dependencies in the output are accurate and verifiable.

---

## 🔧 What It Does

- Parses all `bazel_dep(name = "...", version = "...")` entries in `MODULE.bazel`
- Skips internal dependencies like `rules_cc`
- Fetches the actual `source.json` from the Bazel Central Registry for each module
- Extracts the source archive URL (e.g., a GitHub tarball)
- Writes a `fossa-deps.yaml` with the following structure:

```yaml
remote-dependencies:
  - name: abseil-cpp
    version: 20240116.1
    url: https://github.com/abseil/abseil-cpp/releases/download/20240116.1/abseil-cpp-20240116.1.tar.gz
```

---

## ▶️ How to Use

1. Place `generate_fossa_deps.py` in the root of your Bazel project (where your `MODULE.bazel` lives).
2. Ensure you have Python 3 and `requests` installed:
   ```bash
   pip install requests pyyaml
   ```
3. Run the script:
   ```bash
      python generate_fossa_deps.py
   ```
4. It will create a `fossa-deps.yaml` file in the same directory.

---

## 📁 Output

The generated `fossa-deps.yaml` can be committed alongside your project or passed to FOSSA via its CLI or CI integrations.

---

## 📝 Notes

- This script uses the live GitHub-hosted Bazel Central Registry.
- It assumes all third-party modules listed in `MODULE.bazel` follow standard source layout in the registry.
