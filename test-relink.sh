#!/usr/bin/env bash
# Experimental technical check only; this does not establish license compliance.
set -euo pipefail
app=$(cd "$(dirname "$0")" && pwd)
root=$app
work=${CODI_NGSPICE_WORK:-"$root/.build/circuit-lab-source"}
sdk=${CODI_EMSDK:-"$root/.build/ngspice-emsdk"}
source "$sdk/emsdk_env.sh" >/dev/null 2>&1
export SOURCE_DATE_EPOCH=1735689600 TZ=UTC LC_ALL=C
ng=ngspice-sf-mirror-ngspice-45.2
ee=EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c
if [[ ! -f "$work/$ng/release/src/spice.wasm" || ! -d "$work/$ee/node_modules" ]]; then echo 'Run build-source.sh first and retain its work directory.' >&2; exit 1; fi
scratch=$(mktemp -d "${TMPDIR:-/tmp}/codi-ngspice-relink.XXXXXXXX")
trap 'result=$?; if (( result != 0 )); then tail -30 "$scratch/relink.log" "$scratch/wrapper.log" 2>/dev/null || true; fi; python3 - "$scratch" <<'"'"'PY'"'"'
import shutil,sys
shutil.rmtree(sys.argv[1],ignore_errors=True)
PY' EXIT
cp -a "$work/$ng" "$scratch/$ng"
cp -a "$work/$ee" "$scratch/$ee"
python3 - "$scratch/$ng" "${CODI_RELINK_KLU:-0}" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/frontend/numparam/mystring.c';s=p.read_text();old='Error: DS could not add string %s'
if s.count(old)!=1:raise RuntimeError('relink experiment patch did not match')
p.write_text(s.replace(old,'RELINK-CODI-EXPERIMENT: DS could not add string %s'))
if sys.argv[2] == "1":
    klu=Path(sys.argv[1])/'src/maths/KLU/klu_defaults.c'
    source=klu.read_text()
    marker='    /* parameters */'
    if source.count(marker)!=1:raise RuntimeError('KLU relink experiment patch did not match')
    klu.write_text('#include <stdio.h>\n'+source.replace(
        marker, '    fputs("RELINK-CODI-KLU\\n", stderr);\n'+marker,
    ))
PY
emmake make -C "$scratch/$ng/release/src/frontend/numparam" -j2 > "$scratch/relink.log" 2>&1
if [[ ${CODI_RELINK_KLU:-0} == 1 ]]; then
    emmake make -C "$scratch/$ng/release/src/maths/KLU" -j2 >> "$scratch/relink.log" 2>&1
fi
touch "$scratch/$ng/release/src/ngspice-main.o"
emmake make -C "$scratch/$ng/release/src" -j2 ngspice >> "$scratch/relink.log" 2>&1
python3 - "$scratch/$ng/release/src/spice.wasm" "${CODI_RELINK_KLU:-0}" <<'PY'
from pathlib import Path
import sys
data=Path(sys.argv[1]).read_bytes()
if b'RELINK-CODI-EXPERIMENT' not in data:raise RuntimeError('modified numparam object was not linked')
if sys.argv[2]=='1' and b'RELINK-CODI-KLU' not in data:raise RuntimeError('modified KLU object was not linked')
PY
cp "$scratch/$ng/release/src/spice.wasm" "$scratch/$ee/src/spice.wasm"
cp "$scratch/$ng/release/src/spice.mjs" "$scratch/$ee/src/spice.js"
npm run build --prefix "$scratch/$ee" > "$scratch/wrapper.log" 2>&1
node --input-type=module - "$scratch/$ee/dist/eecircuit-engine.mjs" <<'JS'
import {pathToFileURL} from 'node:url';
const {Simulation}=await import(pathToFileURL(process.argv[2]));const s=new Simulation();await s.start();
const useKlu = process.env.CODI_RELINK_KLU === '1';
s.setNetList('Divider\nV1 in 0 DC 10\nR1 in out 1k\nR2 out 0 1k\n' + (useKlu ? '.options klu\n' : '') + '.op\n.end');
const r=await s.runSim(),v=r.data.find(x=>x.name==='v(out)').values[0];
if(Math.abs(v-5)>1e-8)throw Error('wrong divider result');
if (useKlu && ![...s.getError(),s.getInfo()].join('\n').includes('RELINK-CODI-KLU')) {
  throw Error('The instrumented KLU runtime was not exercised.');
}
console.log('PASS modified Numparam was relinked and still simulates 5 V.');
if (useKlu) console.log('PASS modified KLU was relinked and exercised by the same simulation.');
process.exit(0);
JS
if [[ -n ${CODI_RELINK_OUTPUT:-} ]]; then
  mkdir -p "$CODI_RELINK_OUTPUT"
  cp "$scratch/$ng/release/src/spice.wasm" "$CODI_RELINK_OUTPUT/spice.wasm"
  cp "$scratch/$ee/dist/eecircuit-engine.mjs" "$CODI_RELINK_OUTPUT/eecircuit-engine.mjs"
fi
