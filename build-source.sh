#!/usr/bin/env bash
# Experimental source build; output is local and is not yet a release package.
set -euo pipefail
app_dir=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$app_dir/../../.." && pwd)
work=${CODI_NGSPICE_WORK:-"$root/.build/circuit-lab-source"}
sdk=${CODI_EMSDK:-"$root/.build/ngspice-emsdk"}
ngsha=3aa30022e975bc04e2d9566e62e76d15e108d7b887f520755383ba37464c2324
eesource=e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b
if [[ -e "$work" ]]; then echo "Work directory already exists: $work (choose a fresh CODI_NGSPICE_WORK)" >&2; exit 1; fi
if [[ ! -f "$sdk/emsdk_env.sh" ]]; then echo "Set CODI_EMSDK to an activated Emscripten 4.0.14 SDK." >&2; exit 1; fi
source "$sdk/emsdk_env.sh" >/dev/null 2>&1
if ! emcc --version | head -1 | grep -q '4\.0\.14'; then echo 'Emscripten 4.0.14 required.' >&2; exit 1; fi
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then echo 'The current toolchain pin is for Linux x86_64.' >&2; exit 1; fi
if [[ $(sha256sum "$sdk/upstream/bin/clang" | cut -d' ' -f1) != 5fc2a956e0b2aa53ac73c9fffbfcd73a608a141eca4155682b6ce10c448f6053 ]]; then echo 'Emscripten clang hash mismatch.' >&2; exit 1; fi
if [[ $(sha256sum "$sdk/upstream/bin/wasm-ld" | cut -d' ' -f1) != 605f1231476d92e2abae151c47ff0192d3e84c9d115038d481a4d71e8d110db5 ]]; then echo 'Emscripten wasm-ld hash mismatch.' >&2; exit 1; fi
if [[ $(sha256sum "$sdk/upstream/emscripten/emcc.py" | cut -d' ' -f1) != 5365e4732033cad03b4d402e1799b5b94a34e0f701625d019e6318303c065ead ]]; then echo 'Emscripten driver hash mismatch.' >&2; exit 1; fi
if [[ $(autoconf --version | head -1) != 'autoconf (GNU Autoconf) 2.71' || $(automake --version | head -1) != 'automake (GNU automake) 1.16.5' || $(libtoolize --version | head -1) != 'libtoolize (GNU libtool) 2.4.7' ]]; then echo 'Expected Autoconf 2.71, Automake 1.16.5 and Libtool 2.4.7.' >&2; exit 1; fi
if [[ $(node --version) != v24.19.0 ]]; then echo 'Expected SDK Node 24.19.0.' >&2; exit 1; fi
export SOURCE_DATE_EPOCH=1735689600 TZ=UTC LC_ALL=C
mkdir -p "$work"
python3 - "$work" "$ngsha" "$eesource" <<'PY'
import hashlib,pathlib,sys,tarfile,urllib.request
w=pathlib.Path(sys.argv[1])
items=[('ngspice.tar.gz','https://codeload.github.com/danchitnis/ngspice-sf-mirror/tar.gz/refs/tags/ngspice-45.2',sys.argv[2]),('engine.tar.gz','https://codeload.github.com/eelab-dev/EEcircuit-engine/tar.gz/424c21eb9f9bb91e72c1befe2d7fc2f09641316c',sys.argv[3])]
for name,url,want in items:
 with urllib.request.urlopen(url,timeout=60) as f: data=f.read(100*1024*1024+1)
 if len(data)>100*1024*1024 or hashlib.sha256(data).hexdigest()!=want: raise RuntimeError(f'{name} source hash mismatch')
 file=w/name;file.write_bytes(data)
 with tarfile.open(file) as t:t.extractall(w,filter='data')
PY
src="$work/ngspice-sf-mirror-ngspice-45.2"
engine="$work/EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c"
cd "$src"
bash "$engine/Docker/hicum2_patch.sh"
python3 - "$src" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]);p=root/'configure.ac';s=p.read_text();s=s.replace('-Wno-unused-but-set-variable','-Wno-unused-const-variable').replace('AC_CHECK_FUNCS([time getrusage])','AC_CHECK_FUNCS([time])');p.write_text(s)
p=root/'src/frontend/control.c';s=p.read_text();needle='#include "ngspice/ngspice.h"'
if s.count(needle)!=1:raise RuntimeError('include patch did not match')
s=s.replace(needle,'#include <emscripten.h>\nEM_ASYNC_JS(void, eesim_sleep_hack, (), { if (Module["handleThings"]) { await new Promise((resolve) => { Module["handleThings"](); }); } });\n'+needle)
needle='freewl = wlist = getcommand(string);'
if s.count(needle)!=1:raise RuntimeError('async patch did not match')
p.write_text(s.replace(needle,'eesim_sleep_hack();\n\t\t'+needle))
PY
./autogen.sh > "$work/autogen.log" 2>&1
mkdir release
cd release
emconfigure ../configure --disable-debug --disable-openmp --disable-xspice --disable-osdi --without-x -with-readline=no > "$work/configure.log" 2>&1
python3 - "$engine/Docker/pre.js" <<'PY'
from pathlib import Path
import sys
p=Path('src/Makefile');s=p.read_text();old='$(ngspice_LDADD) $(LIBS)'
if old not in s:raise RuntimeError('link patch did not match')
new=old+' -O2 -s ASYNCIFY=1 -s ASYNCIFY_ADVISE=0 -s ASYNCIFY_IGNORE_INDIRECT=0 -s ENVIRONMENT="web,worker" -s ALLOW_MEMORY_GROWTH=1 -s MODULARIZE=1 -s EXPORT_ES6=1 -s EXPORTED_RUNTIME_METHODS=["FS","Asyncify","callMain"] --pre-js '+sys.argv[1]+' -o spice.mjs'
p.write_text(s.replace(old,new))
PY
emmake make -j"${CODI_BUILD_JOBS:-4}" > "$work/make.log" 2>&1
cp src/spice.mjs "$engine/src/spice.js"
cp src/spice.wasm "$engine/src/spice.wasm"
python3 - "$engine" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/simulationLink.ts';s=p.read_text().splitlines()
s=[line for line in s if not ('from "./circuits.ts"' in line or 'from "./models/' in line)]
s=[line for line in s if not ('module.FS?.writeFile("/modelcard.' in line or 'module.FS?.writeFile("/sm141064.ngspice"' in line)]
p.write_text('\n'.join(s)+'\n')
PY
npm ci --prefix "$engine" --ignore-scripts --no-audit --no-fund
npm run build --prefix "$engine"
python3 - "$engine" "$app_dir" "$work" <<'PY'
import json,pathlib,shutil,sys
engine,app,work=map(pathlib.Path,sys.argv[1:]);dest=app/'node_modules/codi-ngspice'
shutil.rmtree(dest,ignore_errors=True);(dest/'dist').mkdir(parents=True)
shutil.copy2(engine/'dist/eecircuit-engine.mjs',dest/'dist/eecircuit-engine.mjs')
shutil.copy2(engine/'LICENSE',dest/'LICENSE')
(dest/'package.json').write_text(json.dumps({'name':'codi-ngspice','version':'0.0.0-research','license':'MIT','type':'module'})+'\n')
shutil.copy2(engine/'dist/eecircuit-engine.mjs',work/'eecircuit-engine.mjs')
print('Research engine installed in',dest)
print('Retain original archives, patched source, configure/make logs and release objects in',work)
print('This build is NOT cleared for redistribution; see README.')
PY
