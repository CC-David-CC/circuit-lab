# Circuit Lab — source-built candidate, not deployed

This app edits and runs self-contained SPICE netlists locally in a browser
worker. It includes voltage-divider and RC-transient examples, a simple plot,
local upload, and open/save through the desktop's browser-first My files and
account service. This is a text-based circuit editor, not a graphical schematic
or PCB editor. It runs on demand, ends the worker on completion, stop or app
close, and times out after 30 seconds. It accepts one `.op`, `.tran`, `.ac`,
or `.dc` analysis and a limited set of directives; `.include`, `.lib`, and
interactive `.control` commands are not supported. These restrictions are
usability and resource limits, not a security boundary. Difficult simulations
may use significant browser memory before the timeout.

The local candidate uses the desktop confirmation before replacing unsaved
netlists, reports immediate save conflicts, and cancels old simulations when
the netlist changes. A browser test with a simulated worker and file service
checks these guards; it is not an end-to-end account or solver test. Changes
made while a replacement confirmation is open are kept. Repackage the research
source archive after changing the app: the builder audit checks the packaged
app inputs against the current app sources as well as the solver and notices.

The runtime engine is built locally from the pinned sources below; the opaque
prebuilt npm WASM is no longer a dependency. The generated app provides
**Source and relinking materials** and **License notices** links. The source
archive is about 48.5 MB and is fetched only when requested, not on app launch.

## Release status and limits

**Do not deploy this candidate until the source package, notices, and LGPL
relinking approach receive final distribution review.** A cleaned source and
relink package is tested from a separate extracted directory with the original
build tree unavailable. It includes modified source, exact original ngspice
and wrapper source, linkable objects, scripts and notices. The test rebuilds a
modified LGPL `numparam` library, relinks it, verifies its change in the
resulting WASM, and solves the 5 V divider. An earlier KLU relink attempt did not find its marker. A later private
experiment recorded a successful rebuild of modified `KLU_defaults`, a marker
in the relinked WASM and the selected KLU runtime, and a 5 V divider result.
The retained instrumented WASM and matching marker were checked again, but the
runtime experiment was not rerun in this review. Its tested archive has a
different whole-file hash from the current local research archive; its baseline
solver, KLU source, KLU archive and link Makefile hashes match. See
`docs/evidence/circuit-lab-klu-relink-receipt.json` at the repository root.
This evidence does not verify every component or settle distribution terms.
The independently relinked engine also passed
an isolated actual account-server save/sync and fresh phone-sized browser
reopen test. These are technical checks, not a legal determination.

The extracted-directory test used the same Linux x86-64 machine with the pinned
Emscripten SDK installed separately. It downloads lockfile-pinned npm build
packages. It is not a different operating system, a second physical machine,
or an offline-from-empty-machine test. Two clean builds in the same environment
produced identical WASM and wrapper hashes; cross-platform reproducibility is
not established. Phone-sized testing used viewport emulation.

The upstream EEcircuit model cards are important future capability and are
preserved for local development. The current prototype does not yet expose
them: the source build disables model-card injection and `.include` / `.lib`
are blocked. The preserved source includes PTM data identified as Arizona
State University property without an explicit redistribution license in that
file. Do not publish those models until their terms have been verified. See
`MODELS.md` for the library-by-library findings and local preservation steps.

The ngspice configuration disables XSPICE, OSDI and CIDER, but enables KLU and
`frontend/numparam`, identified as LGPL in the
[ngspice 45.2 license inventory](https://github.com/danchitnis/ngspice-sf-mirror/blob/ngspice-45.2/COPYING).
The package includes ngspice's COPYING, the wrapper's MIT license, Emscripten
and runtime notices, and the original SuiteSparse 3.7.0 AMD, BTF, KLU and COLAMD
notices. It includes the AMD attribution and “Used by permission” wording from
its original README. Review the actual linked component inventory, bundled
notices, availability of corresponding sources and the LGPL relinking method
before release; a technical success alone does not settle those obligations.

## Build and package

On the verified Linux x86-64 environment, install and activate Emscripten
4.0.14 separately, then run from the SIMPLIFIED root:

```
CODI_EMSDK=/absolute/path/to/emsdk apps/system/circuit-lab/build-source.sh
npm test --prefix apps/system/circuit-lab
curl -fL https://people.engr.tamu.edu/davis/SuiteSparse/SuiteSparse-3.7.0.tar.gz -o .build/suitesparse-3.7.0.tar.gz
python3 apps/system/circuit-lab/package-source.py --research-allow-unreviewed-models --output apps/system/circuit-lab/node_modules/codi-ngspice/source-relink.zip
```

The final command is for **local research only** and includes full model source
whose redistribution terms remain unresolved. It validates the SuiteSparse notice archive, checks that the
installed wrapper matches the just-built source tree, and creates the on-demand
archive and adjacent `NOTICES.txt`. The normal app builder then includes both
explicitly declared assets. Package only after all source changes are final,
because the archive includes the host integration source and test. The source
and binary must come from the same build. The package checks for workstation
home-directory paths and excludes configure logs, account data, databases and
keys. The archive is a generated build artifact, not source-backup material.

The build requires a fresh `.build/circuit-lab-source` directory. Use
`CODI_NGSPICE_WORK` for another unused location and `CODI_BUILD_JOBS` to set
parallelism. `SOURCE_DATE_EPOCH` is fixed. Original source archives, patched
source, logs and the object tree remain in the build directory for audit.

Pinned inputs:

- ngspice 45.2 source archive SHA-256
  `3aa30022e975bc04e2d9566e62e76d15e108d7b887f520755383ba37464c2324`;
- EEcircuit wrapper commit `424c21eb9f9bb91e72c1befe2d7fc2f09641316c`, source
  archive SHA-256
  `e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b`;
- SuiteSparse 3.7.0 original notice archive SHA-256
  `3340ec0508d0680451bcc7d7581d04942c58b07cc71dfb7e13d0718060c911d9`;
- Emscripten 4.0.14 Linux x86-64 release
  `4658718c188782acc67a249d45fce2d891ee3cc1`, archive SHA-256
  `4f83b1ef38c4d4c6df1ad6d9ae9970fb1f4bda7342c5860868d1825f4460b27c`.

The research SDK was provisioned using emsdk commit
`d7b4130688bfa348392b921ab04015aa15c4f154`, `emsdk install 4.0.14` and
`emsdk activate 4.0.14`. The script checks installed clang, wasm-ld and emcc.py
hashes, not every SDK file; verify the complete archive independently. It also
checks Autoconf 2.71, Automake 1.16.5, Libtool 2.4.7 and SDK Node 24.19.0. The
tested host used Make 4.3 and Python 3.12.3. Two clean builds on that host
produced WASM SHA-256
`c6ad5a9d87a7a1bddc83d23f16918fd6f521c5ed990b1e876bef9835483cb31b`
and wrapper SHA-256
`534904ee934de1ab70050e17cd7b5e1484b9abb2f4721786a5571de23223249b`.

## Independent relink and application tests

To test the packaged materials, choose a new empty destination and run:

```
CODI_EMSDK=/absolute/path/to/emsdk apps/system/circuit-lab/verify-portable.sh \
  apps/system/circuit-lab/node_modules/codi-ngspice/source-relink.zip \
  /absolute/path/to/new-extraction-directory
```

The verifier checks source and binary hashes, relocates generated build paths,
installs the wrapper's lockfile-pinned build dependencies, modifies and
rebuilds the LGPL component in a temporary copy, relinks, and runs the example.
Its `relinked/` output is a test artifact; it is not the original candidate.
The tested archive scan found no workstation home-directory references or
private database/key files.

`python3 apps/system/circuit-lab/test-audit-package.py` runs negative checks
for the technical release gate. `package-source.py` automatically runs
`audit-package.py`, which checks that the wrapper embeds the packaged WASM,
compares notices to pinned sources, checks required relink objects, binds the
installed engine to the source package, and checks every preserved model and
example file against upstream. After the app builder runs, use
`python3 apps/system/circuit-lab/audit-builder.py OUTPUT_DIRECTORY` to check
the actual bundled worker, catalog, source archive and notices together. For
the isolated `arduino-simulator` test alias, add `--app-id arduino-simulator`.
These are technical checks, not a substitute for distribution review.

`tests/circuit-account-browser.test.mjs` exercises a loopback-only isolated
preview, actual account-server synchronization, a fresh phone-sized browser,
and the visible source and notice links. Set `CIRCUIT_SOURCE_PATH` to the
candidate archive so the test compares its hash with the served asset. For
test staging only, build this app under the `arduino-simulator` entry alias,
launch an isolated preview on port 18180, and connect a Chromium debugging
endpoint on port 19255. The test creates a disposable account; do not use a
live or non-loopback server.

The wrapper embeds its WASM as a data URL. The worker decodes that local
payload itself because the desktop's `connect-src 'self'` blocks fetching data
URLs. No site-wide CSP change or network fetch is required for simulation.

The local save-flow candidate asks before replacing a different existing My files
netlist and checks the file version again when writing. Changes made while that
confirmation or save is pending remain unsaved in the editor; after the first
write completes, saving again uses the new file version. A file modified by
another writer during confirmation is not overwritten. Desktop and
phone-sized local tests use an isolated real account service, reopen the synced
netlist in a fresh browser context, and run the actual ngspice divider example.
The test does not cover physical touch, all SPICE models, or every solver error.
Regenerate the matching source and relinking archive before any further
packaging; the distribution-review gate above still applies.
