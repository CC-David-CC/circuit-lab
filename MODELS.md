# Semiconductor model libraries — preserved for development

These upstream model cards are important planned capabilities. They have **not
been deleted**. The pinned source build retains the full upstream wrapper tree
in `.build/circuit-lab-source/EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c/src/models/`.
An independent, hash-verified local development copy is preserved under
`apps/system/circuit-lab/.build/model-source/`; its `PROVENANCE.json` records
individual file hashes. Both are ignored by Git and must not be published as
public assets while licensing is unresolved.

To recover the complete original model and example source from the pinned
upstream archive into a fresh local directory:

```
python3 apps/system/circuit-lab/prepare-models.py
```

Pass `--archive /path/to/engine.tar.gz` to use an existing copy, or `--output`
to select another fresh destination. Existing directories are never replaced.
The required archive has SHA-256
`e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b` and
comes from EEcircuit engine commit `424c21eb9f9bb91e72c1befe2d7fc2f09641316c`.

## Current functionality

The current **unshipped** source-built Circuit Lab deliberately does not load
these libraries: the build patch disables model-card injection, and the app's
netlist validation rejects `.include` and `.lib`. Thus a netlist relying on
these supplied process libraries cannot run in the prototype today. The
ngspice solver remains available for the supported circuit analyses; a user
can write a supported `.model` definition directly in a netlist. A simple
level-1 NMOS operating-point example has been tested against its expected
4.8 V drain voltage; it is illustrative and is not a foundry model. A simple
diode operating-point calculation was also checked. We have not qualified
all device types. No live application was changed by this
research; CircuitJS is separate.

## Initial license and provenance findings

| Library in pinned source | What the source says | Open work |
| --- | --- | --- |
| SkyWater SKY130 (`src/models/skywater/`) | File headers state Apache-2.0; the [SkyWater PDK repository](https://github.com/google/skywater-pdk/blob/main/README.src.rst) also states Apache-2.0. | Verify exact original revision and modifications, retain copyright and required Apache notices, and test compatibility. |
| GlobalFoundries GF180 (`src/models/gf180/`) | File headers state Apache-2.0; the [GF180MCU PDK repository](https://github.com/google/gf180mcu-pdk/blob/main/README.rst) states Apache-2.0. | Verify the exact source and modifications, include required notices, and test ngspice compatibility. |
| FreePDK 45 / 3D45 (`src/models/freepdk/freePDK.ts`) | The header describes Apache-2.0 for most files and a separate SVRF agreement; [NC State](https://eda.ncsu.edu/freepdk/) describes FreePDK as Apache-2.0. | Identify which source material is actually embedded and whether any separate SVRF terms apply. The file calls its 45 nm parameters customized PTM, so review their lineage too. |
| FreePDK 15 (in `freePDK.ts`) | The embedded block contains a three-clause BSD-style notice and says it derives from ASU 14 nm PTM-MG. | Verify that the stated terms cover the precise embedded derived data and preserve any applicable attribution. |
| ASU PTM (`src/models/ptm.ts`) | The header identifies ASU ownership and links to [ptm.asu.edu](https://ptm.asu.edu/), but does not state redistribution terms. | Obtain a reliable grant or other authoritative license for this exact data before public distribution. The cited site was not accessible during this review. Do not infer a grant from the wrapper's MIT license. |
| Example circuits (`src/circuits.ts`) | Upstream examples reference model cards and may contain their own sample parameters. | Review the particular examples and their data provenance when enabling them. |

These are preliminary findings, not legal clearance. The full upstream source is
preserved locally; the unreviewed PTM material must not be silently dropped or
shipped. `package-source.py` refuses to create an archive unless passed its
explicit **local research-only** flag because the full source archive contains
model data with unresolved terms.

## Path to a usable model library

Qualify each model independently, ship only with verified rights and complete
notices, and keep unverified models in local development pending resolution.
Implement a controlled, per-app model resolver for approved packaged cards
instead of arbitrary filesystem includes, then test representative DC,
transient, transistor and process-specific circuits against known results.
Load approved libraries on demand so users do not download every model when
opening the app. Do not present a process model as fabrication-qualified until
its provenance and validity are established.
