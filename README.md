# Circuit Lab — research prototype, do not ship

This independent app edits and runs self-contained SPICE netlists locally in a
browser worker with the EEcircuit ngspice WebAssembly engine. It has a voltage
divider and an RC transient example, a simple plot, upload from the user's
computer, and open/save through the desktop's My files account service. The
application is text-based; it is not a graphical schematic or PCB editor.
It runs on demand, ends the worker on completion, stop, or app close, and stops
a simulation after 30 seconds. It accepts one `.op`, `.tran`, `.ac`, or `.dc`
analysis and a limited set of directives; `.include`, `.lib`, and interactive
`.control` commands are not supported. These restrictions are usability and
resource limits, not a security boundary. Large or difficult simulations may
still use significant browser memory before the timeout.

## Distribution blocker

**Do not add this app to a release until the embedded engine's license and
corresponding sources are verified and distributed.** The npm package
`eecircuit-engine@1.9.0` declares MIT and the app builder includes that wrapper
license, but the package's large JavaScript module also embeds a prebuilt
ngspice WASM binary and model data. The wrapper's MIT notice alone does not
cover them.

The npm metadata identifies wrapper source commit
[`424c21eb9f9bb91e72c1befe2d7fc2f09641316c`](https://github.com/eelab-dev/EEcircuit-engine/tree/424c21eb9f9bb91e72c1befe2d7fc2f09641316c)
and npm integrity `sha512-qmCR+2/sz8nkaCsXL2ZebBua7sff//Zu2zAQq+qkkXLcFjxfpbY1TNRax284UFq6hhi9q2y1E/VxIRhOHWXVA==`.
The simulation banner identifies ngspice 45.2. The corresponding
[ngspice 45.2 license inventory](https://github.com/danchitnis/ngspice-sf-mirror/blob/ngspice-45.2/COPYING)
lists LGPL components, including `src/frontend/numparam`, alongside modified
BSD and other code. GlobalFoundries model data in the wrapper source identifies
Apache-2.0. The npm distribution does not provide a complete set of notices or
verified corresponding source for its embedded binary.

The wrapper commit omits the generated `spice.js` and `.wasm`; its
[build script](https://github.com/eelab-dev/EEcircuit-engine/blob/424c21eb9f9bb91e72c1befe2d7fc2f09641316c/Docker/run.sh)
selects the latest ngspice tag and latest Emscripten at build time rather than
pinning exact inputs. The version banner is evidence of a candidate source
version, not proof of the binary's exact source, patches, or reproducibility.
Before shipping, pin and verify the corresponding ngspice revision, patches,
toolchain, linked components and model sources; provide all applicable notices,
source and relinking/replacement materials as required, and make the app builder
include them in the release. Another option is a reviewed, reproducible local
build with pinned inputs and clearly established notices. This determination is
not complete.

## Development and tests

Run `npm ci --prefix apps/system/circuit-lab --ignore-scripts` and then
`npm test --prefix apps/system/circuit-lab`. The engine test solves a real
10 V equal-resistor divider (5 V) and a real RC step (approximately 4.966 V at
5 ms). An isolated browser build also passed both tests and drew the transient
plot. An isolated actual desktop/account-server test saved and synced the
netlist, then reopened and simulated it in a fresh phone-sized Chrome session.
The latter is viewport emulation, not a physical-device test.

`tests/circuit-account-browser.test.mjs` exercises the real account-server path
against a loopback-only isolated preview. For test staging only, build this app
using the `arduino-simulator` entry alias, launch the isolated preview on port
18180, and connect a Chromium debugging endpoint on port 19255. The test creates
a disposable account. Do not use a live or non-loopback server for this test.

The published engine embeds its WASM as a data URL. The worker decodes that
local payload itself because the desktop's `connect-src 'self'` blocks fetching
data URLs. No site-wide CSP change or network fetch is required. The generated
bundle and node_modules are build outputs and are not source files.
