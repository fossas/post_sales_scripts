# Scanning AOSP and Android Automotive trees with FOSSA

An AOSP checkout is not one project with one lockfile. It is hundreds of git projects assembled by a
`repo` manifest, built by Soong (`Android.bp`) and make, with the product makefile's `PRODUCT_PACKAGES`
deciding which modules land in the system image. No dependency scanner reads Soong. This folder is a
working pattern for getting license and vulnerability coverage of such a tree anyway, in **one
`fossa analyze` run**, and for keeping the declared part of it generated from the tree instead of
maintained by hand.

Third-party code enters an AOSP tree four ways, and each way leaves a different trace:

| How it enters                                          | Where it lives                    | What declares it                                                                       |
| ------------------------------------------------------ | --------------------------------- | -------------------------------------------------------------------------------------- |
| Maven artifacts resolved at build time                 | Gradle caches (never in the tree) | `build.gradle(.kts)` + version catalog                                                 |
| In-tree source copies maintained by `external_updater` | `external/<lib>/`                 | a `METADATA` file (protobuf text: upstream URL, pinned tag or SHA, CPE, license class) |
| Prebuilt jars and aars consumed by Soong               | `prebuilts/**`                    | `Android.bp` `java_import` (a path, no coordinates)                                    |
| Copies made by a team with no process                  | `third_party/`, `libs/`, inline   | nothing                                                                                |

The pattern maps each of those to a FOSSA lane:

| Tree content                                            | FOSSA lane                                                                                             | License data                                 | Vulnerability data                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------- | ------------------------------------------------------------- |
| Gradle app modules                                      | Gradle strategy (fossa-cli runs `./gradlew` with its own init script and reads the resolved classpath) | registry, per artifact                       | per artifact version                                          |
| `external/*` with `METADATA` and a github upstream      | `fossa-deps.yml` `referenced-dependencies` type `git`, **generated** from the METADATA pins            | FOSSA license-scans the upstream at that tag | per version (tag resolved to a commit)                        |
| `external/*` whose upstream is not on github or not git | `fossa-deps.yml` `vendored-dependencies` (directory archived and license-scanned)                      | file scan                                    | via CPE in the optional CycloneDX lane, where the CPE matches |
| prebuilt jars with `META-INF/maven/**/pom.properties`   | `fossa-deps.yml` `referenced-dependencies` type `maven`, **generated** from the jar                    | registry                                     | per version                                                   |
| proprietary or partner code                             | `fossa-deps.yml` `custom-dependencies` (hand-declared)                                                 | declared                                     | none                                                          |
| copies nobody declared                                  | Vendetta (`--x-vendetta`): file hashes matched against FOSSA's component knowledge base                | registry for the identified component        | per identified version                                        |
| copied fragments inside first-party files               | snippet scan (`--snippet-scan`)                                                                        | license of the matched source                | none (provenance signal)                                      |

`Android.bp`, `*.mk` and the repo manifest are not read by any lane. They remain the audit trail for
saying _which_ of the above actually ships.

## What is in this folder

| File                            | Purpose                                                                                                                                                                                                                                                                |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fossa-scan.sh`                 | The scan, the way a CI job runs it: regenerate `fossa-deps.yml`, then `fossa analyze --x-vendetta --snippet-scan`, then `fossa test`. `--dry` analyzes without uploading.                                                                                              |
| `tools/gen-fossa-deps.py`       | Regenerates `fossa-deps.yml` from the tree: git references from `METADATA`, Maven coordinates from each prebuilt jar's `pom.properties`, plus the hand-maintained sections from `fossa-deps.base.yml`. Refuses to write a file with a missing lane (`--check` for CI). |
| `tools/aosp_metadata_scan.py`   | Walks the tree for `METADATA` files and emits the git references, a CycloneDX 1.5 SBOM (all tiers, with the CPEs AOSP records) and a coverage report that says which components could not be promoted and why.                                                         |
| `verify-scan.sh`                | API readback of a revision: build status, issue counts, dependency rows by lane, unresolved rows, licensing active/ignored counts, snippet records. Receipts, not screenshots.                                                                                         |
| `templates/fossa.yml`           | Starting `.fossa.yml`: project identity, discovery scoped to the app, Gradle scoped to the release classpath.                                                                                                                                                          |
| `templates/fossa-deps.base.yml` | Starting `fossa-deps.base.yml`: the vendored and custom sections a team maintains by hand.                                                                                                                                                                             |
| `examples/`                     | A generated `fossa-deps.yml`, `coverage.md` and CycloneDX from a small fictional vendor tree, so you can see the output shape before running anything.                                                                                                                 |

Requirements: fossa-cli 3.20 or newer (developed against 3.20.4), Python 3.10 or newer (standard
library only, no network), and for the Gradle lane the app's build environment: a JDK (17 for AGP 8.x)
and an Android SDK with the platform and build-tools the app's `compileSdk` needs.

## Quick start

From the root of the vendor tree (the directory that contains `external/`, `prebuilts/`, your Gradle
app under `packages/apps/...`, and so on):

```bash
# 1. bring the tooling in
mkdir -p tools
cp /path/to/post_sales_scripts/aosp/tools/*.py tools/
cp /path/to/post_sales_scripts/aosp/fossa-scan.sh .
cp /path/to/post_sales_scripts/aosp/templates/fossa.yml .fossa.yml
cp /path/to/post_sales_scripts/aosp/templates/fossa-deps.base.yml .

# 2. edit .fossa.yml (project id, the app path) and fossa-deps.base.yml (vendored dirs, proprietary code)

# 3. build environment for the Gradle lane
export JAVA_HOME=/path/to/jdk17 ANDROID_HOME=/path/to/android-sdk FOSSA_API_KEY=...

# 4. look before uploading: regenerate fossa-deps.yml and print the discovered units
bash fossa-scan.sh --dry

# 5. the real run: upload, then wait for the issue scan (fossa test)
bash fossa-scan.sh

# 6. receipts for the uploaded revision
bash /path/to/post_sales_scripts/aosp/verify-scan.sh <org-id> <project-id> "$(cat .fossa-out/LAST_REV)"
```

Every run mints a new revision name (`<tree>-<git sha>-<timestamp>`); keep the project id stable and
vary the revision, so FOSSA keeps history per scan.

## How `fossa-deps.yml` is generated

`tools/gen-fossa-deps.py` runs first on every scan and writes `fossa-deps.yml` from three inputs:

1. **`external/*/METADATA`** → `referenced-dependencies` type `git`. `aosp_metadata_scan.py` parses each
   file (both the modern `identifier {}` and the legacy `url {} + version` schema), keeps entries with a
   github upstream and a pin whose shape FOSSA can resolve (a tag or a commit SHA), lowercases the
   repository name (git locator matching is case-sensitive), and passes the pin verbatim; FOSSA resolves
   the tag to a commit server-side. Pins it cannot promote (bare numbers such as `76`, date-style tags,
   non-github or non-git upstreams, homepage-only METADATA) are demoted to the CycloneDX inventory and
   listed with the reason in `coverage.md`, so the gaps are explicit.
2. **`prebuilts/**/*.jar` and `*.aar`** → `referenced-dependencies` type `maven`. Each archive's
   `META-INF/maven/**/pom.properties` yields `groupId:artifactId` and `version`; every properties file in
   a jar is read (shaded jars carry several). A jar without one is reported, not guessed, which is the cue
   to declare it in the base file if it is third-party.
3. **`fossa-deps.base.yml`** is appended verbatim: the `vendored-dependencies` and `custom-dependencies`
   sections, which are judgment calls the tree cannot prove (which directories to archive-scan, what the
   proprietary code is and under which license).

If `prebuilts/` exists but no jar yielded a coordinate, or `external/` exists but no METADATA produced a
git entry, the generator prints the reason, leaves the previous `fossa-deps.yml` in place and exits 2, so
a broken walk cannot silently upload a unit with a missing lane. `--check` exits non-zero when the committed
file no longer matches the tree, which is the CI gate for "someone edited the generated file by hand".

Only names, versions and URLs are produced; the generator makes no network calls.

## Lane notes

**Gradle.** fossa-cli needs the build to resolve: without a JDK, the SDK and reachable repositories it
exits 0 with zero Gradle dependencies, and the fossa-deps unit alone is uploaded. Validate with
`./gradlew :app:dependencies --configuration releaseRuntimeClasspath` before blaming the scan. By
default fossa-cli reads every resolved configuration of every module; test and dev configurations are
excluded by an enumerated list of configuration names, and AGP's internal
`_internal-unified-test-platform-*` configurations are not on that list, so they surface as unresolvable
`com.android.tools.utp:*` rows. The template scopes the lane to `releaseRuntimeClasspath` with
`experimental.gradle.configurations-only`; that key is documented by fossa-cli as experimental and
removable without warning, so pin the CLI version in CI and keep target or path scoping as the fallback.
A `compileOnly(files(...))` jar has no coordinates and never appears in the Gradle lane; declare it in
the base file.

**Vendetta.** Sends MD5 hashes of files only; the component identification runs on FOSSA's side. It
finds libraries copied in with no declaration at all, and it corroborates `METADATA` entries: when the
declared pin and the detected content resolve to the same commit, FOSSA shows one dependency row with
both origins. Treat a detected version as a lead and the METADATA pin as the fact: detections can land one
patch level away from the pin, and a library detected without a version resolves to the upstream's
current head, which hides its vulnerabilities until you pin it (a `METADATA` file or a git entry in the
base file).

**Snippet scan.** Fingerprints first-party source files, and for matched files uploads their content
(retained for 30 days) so the side-by-side view works. Match records populate after the build finishes
processing: minutes for content the corpus has seen, up to an hour for fresh content, and aggregates keep
climbing until processing settles, so do not read counts off a revision that is minutes old. Over
`external/` the scan reports vendored files matching themselves at 100%, which is true and redundant with
METADATA; the signal is in first-party files. The project's snippet auto-reject threshold governs
rejection status, not visibility: sub-threshold records are still listed, flagged as rejected. If you
want the Licensing issues tab to show only dependency-lane items, turn off snippet-derived licensing
issues in the project settings; the Snippets view keeps the findings.

**Optional CycloneDX lane.** `aosp_metadata_scan.py` also writes a CycloneDX 1.5 SBOM with every
METADATA component: github upstreams as `pkg:github` purls, the others with the CPE AOSP records in its
`security { tag: "NVD-CPE2.3:..." }` block (version-refreshed from the pin where that can be derived
safely). `fossa sbom analyze <file> --project <id>-sbom --revision <rev>` imports it as a separate
project. Expect the purl components to duplicate the git lane's findings; CPE-only components only get
vulnerability data where the CPE actually matches NVD's product naming, which is the weaker path.

## Data sent to FOSSA, by lane

| Lane                              | Leaves the machine                                                                                                                                              |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gradle, `referenced-dependencies` | package coordinates and versions                                                                                                                                |
| `vendored-dependencies`           | an archive of the directory (archive-upload scan method) or license-scan results only (CLI-side scan method, `vendoredDependencies.scanMethod: CLILicenseScan`) |
| Vendetta                          | MD5 file hashes                                                                                                                                                 |
| snippet scan                      | fingerprints, plus the full content of files that matched, retained 30 days                                                                                     |
| generators                        | nothing; they run offline                                                                                                                                       |

## Gotchas worth knowing before the first run

- **`.fossa.yml` identity.** `project.id` is the locator; `project.name` is only the display title and is
  honored at project creation. With neither `-p` nor `project.id`, fossa-cli infers an id from the git
  remote, else the SVN root, else the directory name, and creates that project.
- **Path filters and archive uploads.** When the vendored-dependency scan method resolves to archive
  upload (the organization default, or forced), a `vendoredDependencies.licenseScanPathFilters` block
  together with any `vendored-dependencies` entry makes fossa-cli reject the archive upload and drop the
  **entire** fossa-deps unit (every section), while the other units still upload and the exit code stays 0. The signals are the error line and `* fossa-deps file analysis: failed` in the scan summary; a
  `--output` dry run does not exercise this path. Either switch the scan method to `CLILicenseScan` (keeps
  the filters) or leave the filter block out and rely on `.gitignore`, which Vendetta and the snippet scan
  honor anyway. The template leaves it out.
- **Scoping the two first-party engines** is not the same as scoping discovery: `paths.exclude` only
  filters which manifests fossa-cli looks for. Vendetta and the snippet scan follow `.gitignore` and skip
  hidden directories.
- **Tag shapes.** A pin such as `curl-8_12_1` resolves to a commit for license scanning but may not match
  vulnerability data keyed by version; `coverage.md` and the readback script tell you which pins carried
  CVEs.
- **The AOSP walkthrough in the fossa-cli docs** (every top-level directory as a vendored dependency with
  `--exclude-manifest-strategies`) is a licenses-only play that needs roughly 2.5 hours on a 32-core
  machine for a full checkout and switches the Gradle strategy off. The lanes here are additive to it and
  scale to a full tree: the METADATA generator walks hundreds of files in seconds, and Vendetta caches
  hashes so the second scan is fast.

## Verifying a scan

`verify-scan.sh <org-id> <project-id> [revision]` reads back, for one revision: build status, the issue
scan's status and counts by type, dependency rows by fetcher with any unresolved locators (a pin that did
not resolve still counts in the revision's dependency total, so check this list, not the total), the
licensing issue counts split into active and ignored, and the snippet records by top-level path. The
revision defaults to `.fossa-out/LAST_REV`, which `fossa-scan.sh` writes only after a successful analyze
(`LAST_REV_PENDING` while a run is in flight).
