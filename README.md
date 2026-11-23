# Circuit Lab

Circuit Lab edits and simulates self-contained SPICE netlists in a browser worker. It includes voltage-divider, RC transient and basic MOSFET examples, a result table, and a plot for analyses with multiple points. Open and save editable netlists in WebOS Files or import a local text file. The Files workflow retains the opened revision and asks before discarding unsaved changes. Change the path in the editor to save a separate copy.

The browser accepts one `.op`, `.tran`, `.ac`, or `.dc` analysis per netlist. Use built-in device models or declare a model inline with `.model`. The worker stops when the analysis completes, when the user clicks Stop, when the window closes, or after 30 seconds. Complex analyses can use substantial browser memory. The sample MOSFET illustrates a level-1 model. Independently preserved process model data and its review are described in [MODELS.md](MODELS.md).

## Build the browser solver

On Linux x86-64, activate Emscripten 4.0.14 from emsdk commit `d7b4130688bfa348392b921ab04015aa15c4f154`. The build recipe checks the SDK compiler, linker and driver hashes, Node 24.19.0, Autoconf 2.71, Automake 1.16.5 and Libtool 2.4.7. Use a fresh work directory.

```sh
export CODI_EMSDK=/absolute/path/to/emsdk
export CODI_NGSPICE_WORK="$PWD/.build/circuit-lab-source"
bash build-source.sh
npm test
```

The solver uses [ngspice 45.2](https://github.com/danchitnis/ngspice-sf-mirror/tree/ngspice-45.2) at archive SHA-256 `3aa30022e975bc04e2d9566e62e76d15e108d7b887f520755383ba37464c2324` and the [EEcircuit wrapper](https://github.com/eelab-dev/EEcircuit-engine/tree/424c21eb9f9bb91e72c1befe2d7fc2f09641316c) at archive SHA-256 `e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b`. The build keeps Numparam and KLU and disables XSPICE, OSDI and CIDER. The patch removes the wrapper's process model imports and injection. The worker decodes the embedded WASM locally under the existing WebOS content policy.

## Assemble and verify a release

Keep the intermediate research ZIP in a private build directory. The browser ZIP takes the audited ngspice sources, linkable objects, the wrapper's build inputs, and the selected license notices. It excludes the original wrapper archive, process model cards, and model-dependent examples. The public bundle links to the browser ZIP and notices for on-demand download.

```sh
mkdir -p .build
curl -fL https://people.engr.tamu.edu/davis/SuiteSparse/SuiteSparse-3.7.0.tar.gz -o .build/suitesparse-3.7.0.tar.gz
python3 package-source.py --work "$CODI_NGSPICE_WORK" --sdk "$CODI_EMSDK" \
  --suitesparse .build/suitesparse-3.7.0.tar.gz \
  --research-allow-unreviewed-models --output .build/private/source-relink.zip
python3 package-browser-release.py --research .build/private/source-relink.zip \
  --engine node_modules/codi-ngspice/dist/eecircuit-engine.mjs \
  --research-notices .build/private/NOTICES.txt --output node_modules/codi-ngspice
bash verify-portable.sh node_modules/codi-ngspice/source-relink.zip .build/relink-verification
```

The packaging script checks the original SuiteSparse 3.7.0 archive at SHA-256 `3340ec0508d0680451bcc7d7581d04942c58b07cc71dfb7e13d0718060c911d9`. The browser verifier extracts the published materials into an empty directory, rebuilds modified Numparam and KLU code, relinks the WASM, rebuilds the wrapper, and runs the 5 V divider through the instrumented KLU solver. It uses the separately installed pinned SDK and lockfile-pinned npm dependencies.

Use the WebOS App Builder with `apps: ["circuit-lab"]` and the component's `app.json`. From this app directory, run `python3 audit-builder.py OUTPUT_DIRECTORY` to match the built worker and launcher source with the downloadable materials. Verify that both Anon and signed-in Chromium can edit, simulate, save, reopen and revise the netlist, and that a signed-in conflict preserves both revisions.
