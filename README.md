# Circuit Lab — research prototype, do not ship

This independent app edits and runs self-contained SPICE netlists locally in a
browser worker. It has voltage-divider and RC-transient examples, a simple
plot, local upload, and open/save through the desktop's My files account
service. This is a text-based circuit editor, not a graphical schematic or PCB
editor. It runs on demand and terminates the worker on completion, stop or app
close. It accepts one `.op`, `.tran`, `.ac`, or `.dc` analysis and a limited
set of directives; `.include`, `.lib`, and interactive `.control` commands are
not supported. These restrictions are usability and resource limits, not a
security boundary. Large analyses may use significant browser memory before
the 30-second timeout.

## Distribution blocker

**Do not add this app to a release until the LGPL source and relinking or
replacement requirements have been reviewed, packaged and tested.** The
first prototype used the prebuilt `eecircuit-engine@1.9.0` npm package, whose
MIT wrapper notice did not establish the source and licenses of the embedded
ngspice binary or model cards. That opaque package is no longer a dependency;
the app imports only the local `codi-ngspice` research build described below.

A source-built candidate has passed a 5 V divider and an RC transient test,
and an isolated real desktop/account-server test saved and synced a circuit,
then reopened and ran it in a fresh phone-sized Chrome context. Phone-sized
means viewport emulation, not a physical phone. These tests establish behavior,
not legal clearance, full ngspice feature support, or cross-system reproducibility.

## Pinned research build

The recipe is `build-source.sh`; it only writes generated files under an
ignored work directory and `node_modules/codi-ngspice`. It fetches and verifies:

- ngspice 45.2 source archive, SHA-256
  `3aa30022e975bc04e2d9566e62e76d15e108d7b887f520755383ba37464c2324`;
- EEcircuit wrapper source commit `424c21eb9f9bb91e72c1befe2d7fc2f09641316c`,
  archive SHA-256
  `e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b`;
- Emscripten 4.0.14, release `4658718c188782acc67a249d45fce2d891ee3cc1`,
  Linux x86-64, with checked SHA-256 values for clang, wasm-ld and emcc.py.

The recipe applies the wrapper's HICUM2 removal and asynchronous input
patches, disables XSPICE, OSDI, CIDER and bundled model-card injection, fixes
`SOURCE_DATE_EPOCH`, and builds with four jobs by default. The tested host has
Autoconf 2.71, Automake 1.16.5, Libtool 2.4.7, Make 4.3, Python 3.12.3, and
SDK Node 24.19.0; exact versions of the first three and Node are checked. The
fixed Emscripten SDK must be installed and activated separately. From the
SIMPLIFIED root:

```
CODI_EMSDK=/absolute/path/to/emsdk apps/system/circuit-lab/build-source.sh
npm test --prefix apps/system/circuit-lab
```

The research SDK was installed using the emsdk repository at commit
`d7b4130688bfa348392b921ab04015aa15c4f154` and `emsdk install 4.0.14` /
`emsdk activate 4.0.14`. The Linux x86-64 release archive for that SDK resolved
to `4658718c188782acc67a249d45fce2d891ee3cc1` and had SHA-256
`4f83b1ef38c4d4c6df1ad6d9ae9970fb1f4bda7342c5860868d1825f4460b27c`.
The build script checks selected installed executable hashes, not every file
in the SDK; verify the full SDK archive independently when provisioning it.

The script requires a fresh work directory. Set `CODI_NGSPICE_WORK` to another
unused path for a second build; `CODI_BUILD_JOBS` controls parallelism. The
build leaves original source archives, patched source, configure/make logs and
the compiled object tree in its work directory for audit. Both the manual
research build and one clean scripted build passed the solver and browser/
account tests. The scripted build produced ngspice WASM SHA-256
`c6ad5a9d87a7a1bddc83d23f16918fd6f521c5ed990b1e876bef9835483cb31b`
and wrapper SHA-256
`534904ee934de1ab70050e17cd7b5e1484b9abb2f4721786a5571de23223249b`.
A second clean scripted build must be compared before calling the recipe
reproducible. Generated dependencies, WASM and object files are not
source-backup material.

For a bounded development-tree relink experiment, run
`apps/system/circuit-lab/test-relink.sh` after a successful source build. It
copies the retained build tree to temporary storage, modifies an LGPL
`numparam` diagnostic string, rebuilds that library and relinks the existing
objects, checks that the changed string is in the resulting WASM, and runs the
5 V divider through the rebuilt wrapper. Both the original manual and the
scripted experiment passed. This checks technical relinking in a retained
development tree; its generated Makefiles still refer to the original build
path. It does not show that an independent recipient has all required inputs.

The source-build candidate is deliberately not a distribution package. It
does not yet include a tested complete corresponding-source archive, all
notices, or a verified method and materials to modify and relink or replace
LGPL components. The ngspice configuration disables XSPICE, OSDI and CIDER,
but includes KLU and `frontend/numparam`, which the
[ngspice 45.2 license inventory](https://github.com/danchitnis/ngspice-sf-mirror/blob/ngspice-45.2/COPYING)
identifies as LGPL. Audit the actual linked components, package appropriate
license texts and corresponding source, and prove the replacement/relink
workflow before shipping. A separate legal review may be appropriate.

## Tests

`npm test --prefix apps/system/circuit-lab` runs the real source-built engine
against the divider and RC examples. Build the engine first. The durable
`tests/circuit-account-browser.test.mjs` exercises a loopback-only isolated
preview, actual account-server synchronization, and a fresh phone-sized
browser. For test staging only, build this app under the `arduino-simulator`
entry alias, launch an isolated preview on port 18180, and connect a Chromium
debugging endpoint on port 19255. The test creates a disposable account. Do not
use a live or non-loopback server for it.

The engine wrapper embeds its WASM as a data URL. The worker decodes that local
payload itself because the desktop's `connect-src 'self'` blocks fetching data
URLs. No site-wide CSP change or network fetch is required for simulation.
