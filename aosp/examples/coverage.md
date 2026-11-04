# AOSP METADATA coverage report

Scanned root: `vendor-tree`
METADATA files parsed: 7
METADATA files skipped by the directory skip-list (.ccache, .git, .repo, out, testdata, tests): 0

Tier-1 verification step (run after the upload): `GET /api/revisions/<url-encoded revision locator>/dependencies` and assert every row's `resolved` is true — the revision-level `dependency_count` does NOT tell you whether a pin actually resolved.

| Tier | Meaning | Count |
| --- | --- | --- |
| 1 | github upstream + resolvable-shaped version -> fossa-deps git dep (license + CVE; verify `resolved` post-upload) | 5 |
| 2 | non-github upstream, demoted pin, and/or CPE -> SBOM inventory (CVE via CPE where present; **no license data**) | 2 |
| 3 | no upstream version -> SBOM inventory only, needs human | 0 |
| 0 | first-party METADATA (no third_party block), skipped — paths listed below for audit | 0 |

| Component | Tier | Upstream | Version | CPE | AOSP license_type | Note |
| --- | --- | --- | --- | --- | --- | --- |
| curl | 1 | https://github.com/curl/curl/ | curl-8_12_1 | cpe:2.3:a:haxx:curl:8.12.1:*:*:*:*:*:*:* | NOTICE |  |
| expat | 1 | https://github.com/libexpat/libexpat/ | R_2_5_0 | cpe:2.3:a:libexpat_project:libexpat:2.5.0:*:*:*:*:*:*:* | BY_EXCEPTION_ONLY |  |
| libpng | 1 | https://github.com/glennrp/libpng.git | v1.6.44 | cpe:2.3:a:libpng:libpng:1.6.44:*:*:*:*:*:*:* | NOTICE |  |
| zlib | 1 | https://github.com/madler/zlib | v1.2.13 | cpe:2.3:a:zlib:zlib:1.2.13:*:*:*:*:*:*:* | NOTICE |  |
| zstd | 1 | https://github.com/facebook/zstd | v1.5.7 |  | RESTRICTED |  |
| SQLite | 2 | https://www.sqlite.org | 3.42.0 | cpe:2.3:a:sqlite:sqlite:3.42.0:*:*:*:*:*:*:* | NOTICE |  |
| freetype | 2 | git://git.sv.nongnu.org/freetype/freetype2.git | 2.13.2 | cpe:2.3:a:freetype:freetype:2.13.2:*:*:*:*:*:*:* | RESTRICTED |  |
