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

| Tree content                                            | FOSSA lane                                                                                                                                   | License data                                 | Vulnerability data                                                              |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------- |
| Gradle app modules                                      | Gradle strategy (fossa-cli runs `./gradlew` with its own init script and reads the resolved classpath)                                       | registry, per artifact                       | per artifact version                                                            |
| `external/*` with `METADATA` and a github upstream      | `fossa-deps.yml` `referenced-dependencies` type `git`, **generated** from the METADATA pins                                                  | FOSSA license-scans the upstream at that tag | per version (tag resolved to a commit)                                          |
| `external/*` whose upstream is not on github or not git | `fossa-deps.yml` `vendored-dependencies` (directory archived and license-scanned), **hand-declared** for every tier-2/3 row in `coverage.md` | file scan                                    | via CPE in the optional CycloneDX lane, only where the CPE matches NVD's naming |
| prebuilt jars with `META-INF/maven/**/pom.properties`   | `fossa-deps.yml` `referenced-dependencies` type `maven`, **generated** from the jar                                                          | registry                                     | per version                                                                     |
| proprietary or partner code                             | `fossa-deps.yml` `custom-dependencies` (hand-declared)                                                                                       | declared                                     | none                                                                            |
| copies nobody declared                                  | Vendetta (`--x-vendetta`): file hashes matched against FOSSA's component knowledge base                                                      | registry for the identified component        | per identified version (see "Lane notes")                                       |
| copied fragments inside first-party files               | snippet scan (`--snippet-scan`)                                                                                                              | license of the matched source                | none (provenance signal)                                                        |

`Android.bp`, `*.mk` and the repo manifest are not read by any lane. They remain the audit trail for
saying _which_ of the above actually ships.

## What is in this folder

| File                                       | Purpose                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fossa-scan.sh`                            | The scan as a CI job runs it: regenerate `fossa-deps.yml`, `fossa analyze --x-vendetta --snippet-scan`, fail if the fossa-deps unit was dropped or if a Gradle unit was expected (a Gradle build file exists; override with `FOSSA_EXPECT_GRADLE=0/1`) and did not succeed, then `fossa test` (its exit code is the script's unless `FOSSA_TEST_SOFT_FAIL=1`). `--dry` analyzes without uploading.      |
| `tools/gen-fossa-deps.py`                  | Regenerates `fossa-deps.yml` from the tree: git references from `METADATA`, Maven coordinates from each prebuilt jar's `pom.properties`, plus the hand-maintained sections from `fossa-deps.base.yml`. Exits 2 instead of writing a file with a missing lane (`--allow-empty-lanes` overrides, `--check` for CI).                                                                                       |
| `tools/aosp_metadata_scan.py`              | Walks the tree for `METADATA` files and emits the git references, a CycloneDX 1.5 SBOM (all tiers, with the CPEs AOSP records) and a coverage report that says which components could not be promoted and why. `--pilot N` emits only the first N components into both outputs, for a first run on a new FOSSA instance.                                                                                |
| `tests/test_shapes.py` + `tests/testdata/` | The generator's suite: the pin-shape scenario table, both METADATA schemas, and a run over 19 real AOSP METADATA files asserting the recorded tier split (`parsed=19 tier1=8 tier2=9 tier3=2`). Run `python3 test_shapes.py` from `tests/`. Keep `tests/` out of any tree you scan: the fixtures are real METADATA files, and the generator skips `tests/` and `testdata/` directories as a safety net. |
| `verify-scan.sh`                           | API readback of a revision: build status, issue counts, dependency rows by lane, unresolved rows, licensing active/ignored counts, snippet records. Receipts, not screenshots.                                                                                                                                                                                                                          |
| `templates/fossa.yml`                      | Starting `.fossa.yml`: project identity, discovery scoped to the app, Gradle scoped to the release classpath.                                                                                                                                                                                                                                                                                           |
| `templates/fossa-deps.base.yml`            | Starting `fossa-deps.base.yml`: the vendored and custom sections a team maintains by hand.                                                                                                                                                                                                                                                                                                              |
| `examples/`                                | The generated `fossa-deps.yml`, `coverage.md` and CycloneDX from the small fictional vendor tree the receipts below come from, so you can see the output shape before running anything.                                                                                                                                                                                                                 |

### Requirements

- fossa-cli **3.20.1 or newer** (developed against 3.20.4). 3.20.1 is the floor because it fixed Vendetta and
  snippet scanning honoring `.gitignore` and skipping hidden directories (fossa-cli #1801), which the
  scoping advice below relies on.
- Python **3.10 or newer**, standard library only, no network.
- For the Gradle lane: the app's build environment, a JDK (17 for AGP 8.x) and an Android SDK with the
  platform and build-tools the app's `compileSdk` needs.
- FOSSA-side entitlements: **snippet scanning** must be enabled for your organization and is available to
  Enterprise customers only; `fossa sbom analyze` (the optional CycloneDX lane) is Enterprise only. There is
  no client-side check, so on an organization without the entitlement drop `--snippet-scan` from
  `fossa-scan.sh`; the other lanes are unaffected.

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

# 6. receipts for the uploaded revision (your org id is the number in the UI's project URLs, custom+<org-id>/...)
bash /path/to/post_sales_scripts/aosp/verify-scan.sh <org-id> <project-id> "$(cat .fossa-out/LAST_REV)"
```

Every run mints a new revision name (`<tree>-<git sha>-<timestamp>`); keep the project id stable and
vary the revision, so FOSSA keeps history per scan. Do the first full run by hand, not in CI: Vendetta
and the snippet scan are expensive the first time they see a tree and cheap afterwards (below).

## How `fossa-deps.yml` is generated

`tools/gen-fossa-deps.py` runs first on every scan and writes `fossa-deps.yml` from three inputs:

1. **`external/*/METADATA`** → `referenced-dependencies` type `git`. `aosp_metadata_scan.py` parses each
   file (both the modern `identifier {}` and the legacy `url {} + version` schema), keeps entries with a
   github upstream and a pin whose shape resolves (a tag or a commit SHA), lowercases the repository name
   (git locators that differ only in case are distinct components in FOSSA; observed 2026-11-04 when
   `DaveGamble/cJSON` and `davegamble/cjson` came back as two rows), and passes the pin verbatim; FOSSA
   resolves the tag to a commit server-side. Pins it cannot promote (bare numbers such as `76`, date-style
   tags, non-github or non-git upstreams, homepage-only METADATA) are demoted to the CycloneDX inventory and
   listed with the reason in `coverage.md`. **Every tier-2 or tier-3 row in `coverage.md` needs a
   hand-added `vendored-dependencies` entry in the base file if you want its license scanned; the
   generator does not add them.**
2. **`prebuilts/**/*.jar` and `*.aar`** → `referenced-dependencies` type `maven`. A jar's
   `META-INF/maven/**/pom.properties` yields `groupId:artifactId` and `version`; every properties file in
   a jar is read (shaded jars carry several). For an AAR the nested `classes.jar` is opened too. Most AARs
   published by Gradle carry no `pom.properties` anywhere, and neither do hand-built jars, so expect
   `note:` lines for those; each one is the cue to declare the archive in the base file if it is
   third-party.
3. **`fossa-deps.base.yml`** is appended verbatim: the `vendored-dependencies` and `custom-dependencies`
   sections, which are judgment calls the tree cannot prove (which directories to archive-scan, what the
   proprietary code is and under which license). The generator appends it verbatim, so any other
   `fossa-deps.yml` section you need, such as `fork-aliases`, can live there as well.

Exit codes: 0 when the file was written or already matched; 2 when `prebuilts/` exists but no archive
yielded a coordinate, or `external/` exists but no METADATA produced a tier-1 git entry, or the previous `fossa-deps.yml`
carried a lane (git or maven) that this walk produced none of, whatever the directory layout (the reason is
printed, the previous `fossa-deps.yml` is left in place, `--allow-empty-lanes` overrides); 1 when the
METADATA generator itself crashed. `--check` exits 2 when the committed file no longer matches the tree (same class as an empty lane: regenerate and commit),
which is the CI gate for "someone edited the generated file by hand".

Only names, versions and URLs are produced; the generator makes no network calls.

## Lane notes

**Gradle.** fossa-cli needs the build to resolve: without a JDK, the SDK and reachable repositories it
exits 0 with no Gradle unit, and the fossa-deps unit alone is uploaded; `fossa-scan.sh` fails the run in that case when a
Gradle build file exists (`FOSSA_EXPECT_GRADLE`). Validate with
`./gradlew :app:dependencies --configuration releaseRuntimeClasspath` before blaming the scan. By
default fossa-cli reads every resolved configuration of every module; test and dev configurations are
excluded by an enumerated list of configuration names (exact matches), and AGP's internal
`_internal-unified-test-platform-*` configurations are not on that list, so they surface as unresolvable
`com.android.tools.utp:*` rows. The template scopes the lane to `releaseRuntimeClasspath` with
`experimental.gradle.configurations-only`; fossa-cli documents that key as experimental and removable
without warning, so pin the CLI version in CI and keep target or path scoping as the fallback. A
`compileOnly(files(...))` jar has no coordinates and never appears in the Gradle lane; declare it in the
base file.

**Vendetta.** Sends MD5 hashes of files only; the component identification runs on FOSSA's side. It
finds libraries copied in with no declaration at all, and it corroborates `METADATA` entries. Read its
results with two things in mind:

- _One library often produces two rows._ When the declared pin and the detected content resolve to the
  same commit, FOSSA shows one row with both origins; when they differ, you get two rows for one library:
  pin commit versus detected commit (one patch level apart is common), the upstream repository versus the
  fork it was detected as, or the same repository in two name casings. On the test tree behind the
  receipts below, one of four overlapping components collapsed to a single row and three did not, and
  one undeclared library (cJSON) came back as two rows differing only in case, each with its own
  vulnerability issues. Expect inflated row and issue counts until you reconcile them; `fork-aliases` in
  `fossa-deps.yml` is the documented lever for mapping a fork or alias onto its base component, and it
  can live in the base file.
- _Treat a detected version as a lead and the METADATA pin as the fact._ A library detected without a
  version resolves to the upstream's current head, so the vulnerabilities reported are those of today's
  upstream rather than of the code in your tree, inaccurate in both directions. On the test tree the four
  version-less detections still carried 23 vulnerability issues, attributed to whatever each upstream's head was
  on the scan date (commits from two days to seven weeks old). Pin it (a `METADATA` file, or a git entry in the base file) to get version-true data.

**Snippet scan.** Fingerprints first-party source files, and for matched files uploads their content
(retained for 30 days) so the side-by-side view works. Match records populate after the build finishes
processing: minutes for content the corpus has seen, up to an hour for fresh content, and aggregates keep
climbing until processing settles, so do not read counts off a revision that is minutes old. Over
`external/` the scan reports vendored files matching themselves at 100%, which is true and redundant with
METADATA; the signal is in first-party files. The project's snippet auto-reject threshold governs
rejection status, not visibility: sub-threshold records are still listed, flagged as rejected. If you
want the Licensing issues tab to show only dependency-lane items, turn off snippet-derived licensing
issues in the project settings; the Snippets view keeps the findings.

**Cost of the first scan.** The generator and the fossa-deps lanes take seconds at any tree size. Vendetta
and the snippet scan hash or fingerprint every file and look each one up; fossa-cli's own documentation
gives roughly 60 minutes for a first scan of the Linux kernel for either engine, and a full AOSP checkout
is larger than that. Results are cached per file content, so the second scan of the same tree, and every
scan where only a few files changed, is fast. Run the first scan manually, then wire CI.

**Optional CycloneDX lane.** `aosp_metadata_scan.py` also writes a CycloneDX 1.5 SBOM with every
METADATA component: github upstreams as `pkg:github` purls, the others with the CPE AOSP records in its
`security { tag: "NVD-CPE2.3:..." }` block (version-refreshed from the pin where that can be derived
safely). `fossa sbom analyze <file> --project <id>-sbom --revision <rev>` imports it as a separate
project. Expect the purl components to duplicate the git lane's findings; CPE-only components only get
vulnerability data where the CPE matches NVD's product naming, which is the weaker path (on the test
tree, both CPE-only components returned nothing).

## Data sent to FOSSA, by lane

| Lane                                                                                              | Leaves the machine                                                                                                     | Retention                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gradle, `referenced-dependencies`                                                                 | package coordinates and versions                                                                                       | n/a                                                                                                                                                                                          |
| `vendored-dependencies`, archive-upload scan method (the usual organization default)              | an archive of the directory, license-scanned on FOSSA's servers                                                        | fossa-cli's vendored-dependencies documentation: files that contain no license text are removed after 30 days; its fossa-deps reference says 2 weeks. Confirm the current figure with FOSSA. |
| `vendored-dependencies`, CLI-side scan method (`vendoredDependencies.scanMethod: CLILicenseScan`) | license-scan results only                                                                                              | n/a                                                                                                                                                                                          |
| Vendetta                                                                                          | MD5 hashes of files                                                                                                    | stored permanently (fossa-cli documentation, Vendetta, "Data Retention")                                                                                                                     |
| snippet scan                                                                                      | CRC64 hashes of all files (to skip known files), fingerprints of new files, and the full content of files that matched | fingerprints permanent; matched content 30 days                                                                                                                                              |
| generators                                                                                        | nothing; they run offline                                                                                              | n/a                                                                                                                                                                                          |

## Gotchas worth knowing before the first run

- **`.fossa.yml` identity.** `project.id` is the locator; `project.name` is only the display title and is
  honored at project creation. With neither `-p` nor `project.id`, fossa-cli infers an id from the git
  remote, else the SVN root, else the directory name, and creates that project.
- **Path filters and archive uploads.** When the vendored-dependency scan method resolves to archive
  upload (the organization default, or forced), a `vendoredDependencies.licenseScanPathFilters` block
  together with any `vendored-dependencies` entry makes fossa-cli reject the archive upload and drop the
  **entire** fossa-deps unit (every section), while the other units still upload and the exit code stays 0. The signals are the error line and `* fossa-deps file analysis: failed` in the scan summary;
  `fossa-scan.sh` greps for that line and fails the run. A `--output` dry run does not exercise this path.
  Either switch the scan method to `CLILicenseScan` (keeps the filters) or leave the filter block out and
  rely on `.gitignore`, which Vendetta and the snippet scan honor from fossa-cli 3.20.1. The template leaves
  it out.
- **Scoping the two first-party engines** is not the same as scoping discovery: `paths.exclude` only
  filters which manifests fossa-cli looks for. Vendetta and the snippet scan follow `.gitignore` and skip
  hidden directories.
- **Tag shapes.** Observed on app.fossa.com on 2026-11-04 with fossa-cli 3.20.4: a pin such as
  `curl-8_12_1` resolves to a commit for license scanning but matched no vulnerability data keyed by
  version, and date-style pins (`20240116`) did not match either; `coverage.md` names the pins the
  generator demoted and `verify-scan.sh` shows which rows carried issues. Re-check these when FOSSA's
  matcher changes; they are observations, not guarantees.
- **Custom-dependency license values.** Observed 2026-11-04: `proprietary-license` and SPDX ids such as
  `MIT` read back as licenses; `Proprietary` (the value fossa-cli's own fossa-deps reference uses in its
  example) and `LicenseRef-...` values read back empty and the row shows as an unlicensed dependency until
  you conclude its license in the UI.
- **The AOSP walkthrough in the fossa-cli docs** (every top-level directory as a vendored dependency with
  `--exclude-manifest-strategies`) is a licenses-only play that needs roughly 2.5 hours on a 32-core
  machine for a full checkout and switches the Gradle strategy off. The lanes here are additive to it;
  see "Cost of the first scan" above before sizing a CI job.

## Verifying a scan

`verify-scan.sh <org-id> <project-id> [revision] [branch]` reads back, for one revision: build status, the
issue scan's status and counts by type, dependency rows by fetcher with any unresolved locators (a pin that
did not resolve still counts in the revision's dependency total, so check this list, not the total), the
licensing issue counts split into active and ignored, and the snippet records by top-level path. The
revision defaults to `.fossa-out/LAST_REV`, which `fossa-scan.sh` writes only after a successful analyze
in which every unit succeeded (`LAST_REV_PENDING` while a run is in flight). A revision scanned without `--snippet-scan` (an
organization without the entitlement) reports no snippet records; the script says so and exits 0, which is expected,
not a failure.

Receipts from the fictional test tree behind `examples/` (a five-module Gradle app, seven `external/`
projects with real AOSP METADATA files and real upstream sources, two copied-in C libraries without
METADATA, four prebuilt jars, a proprietary SDK stub), read back with this script: 148 dependency rows
(131 Maven, 13 git, 3 archive, 1 custom), 0 unresolved, 116 issues (99 vulnerability), licensing 5 active
and 36 auto-ignored, 102 snippet records. One note: that revision uploaded the custom dependency with a `LicenseRef-` value (read back empty); the `examples/` and the template carry the `proprietary-license` value that resolves, which postdates the receipt.
