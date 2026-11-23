#!/usr/bin/env bash
# Unpack the source and relink package in a fresh location and exercise it.
set -euo pipefail
if [[ $# -ne 2 ]]; then echo 'Usage: verify-portable.sh PACKAGE.zip NEW_EMPTY_DIRECTORY' >&2; exit 2; fi
archive=$(realpath "$1")
target=$2
sdk=${CODI_EMSDK:?Set CODI_EMSDK to the activated pinned Emscripten SDK}
if [[ -e "$target" ]]; then echo 'Target already exists; choose a fresh directory.' >&2; exit 1; fi
mkdir -p "$target"
target=$(cd "$target" && pwd)
python3 - "$archive" "$target" "$sdk" <<'PY'
import hashlib,json,os,pathlib,stat,sys,zipfile
archive,target,sdk=map(pathlib.Path,sys.argv[1:])
with zipfile.ZipFile(archive) as z:
 entries=z.infolist()
 if len(entries)>20000 or sum(entry.file_size for entry in entries)>1024**3:
  raise RuntimeError('archive exceeds verification limits')
 names=[entry.filename for entry in entries]
 if len(names)!=len(set(names)):raise RuntimeError('duplicate archive entry')
 meta=json.loads(z.read('package.json'))
 if meta.get('format') not in {'codi-ngspice-research/1','codi-ngspice-browser/1'}:
  raise RuntimeError('unexpected package format')
 if meta['ngspice']!='ngspice-sf-mirror-ngspice-45.2' or meta['engine']!='EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c':
  raise RuntimeError('unexpected component source pins')
 if meta['format']=='codi-ngspice-browser/1':
  if set(meta['archives'])!={'ngspice.tar.gz'} or meta.get('modelLicenses')!='excluded':
   raise RuntimeError('unexpected browser source metadata')
  wrapper='work/'+meta['engine']+'/'
  if 'work/engine.tar.gz' in names or any(n.startswith(wrapper+'src/models/') or n==wrapper+'src/circuits.ts' for n in names):
   raise RuntimeError('private model data cannot be included in the browser package')
 for info in entries:
  p=pathlib.PurePosixPath(info.filename)
  if p.is_absolute() or '..' in p.parts or not p.parts:raise RuntimeError('unsafe archive path')
  if info.file_size > 256*1024*1024:raise RuntimeError('archive entry too large')
  z.extract(info,target)
  path=target.joinpath(*p.parts)
  if path.is_file():path.chmod((info.external_attr >> 16)&0o777 or 0o644)
old=meta['workPathToken'].encode();sdk_token=meta['sdkPathToken'].encode();new=str(target/'work').encode()
if not set(meta['archives'])<={'ngspice.tar.gz','engine.tar.gz'}:raise RuntimeError('unexpected source archive name')
for name,want in meta['archives'].items():
 if hashlib.sha256((target/'work'/name).read_bytes()).hexdigest()!=want:raise RuntimeError('source archive hash mismatch')
for file,key in [(target/'work'/meta['ngspice']/'release/src/spice.wasm','wasmSha256'),(target/'work'/meta['engine']/'dist/eecircuit-engine.mjs','wrapperSha256')]:
 if hashlib.sha256(file.read_bytes()).hexdigest()!=meta[key]:raise RuntimeError('built artifact hash mismatch')
for file,key in [(sdk/'upstream/bin/clang','clangSha256'),(sdk/'upstream/bin/wasm-ld','wasmLdSha256')]:
 if hashlib.sha256(file.read_bytes()).hexdigest()!=meta[key]:raise RuntimeError('SDK executable hash mismatch')
if old!=b'@CODI_WORK@' or sdk_token!=b'@CODI_EMSDK@':raise RuntimeError('invalid path tokens')
changed=0
for p in (target/'work').rglob('*'):
 if not p.is_file():continue
 data=p.read_bytes()
 if b'\0' in data:continue
 if old in data or sdk_token in data:p.write_bytes(data.replace(old,new).replace(sdk_token,str(sdk).encode()));changed+=1
if not changed:raise RuntimeError('no generated build paths found to relocate')
# Zip extraction does not preserve dependency ordering; equal timestamps keep
# make from re-running configure solely because files landed in a new folder.
for p in (target/'work').rglob('*'):
 if p.is_file():os.utime(p,(1735689600,1735689600))
print('Relocated paths in',changed,'build files')
PY
source "$sdk/emsdk_env.sh" >/dev/null 2>&1
engine="$target/work/EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c"
npm ci --prefix "$engine" --ignore-scripts --no-audit --no-fund
if python3 - "$target/package.json" <<'PY'
import json,sys
with open(sys.argv[1]) as source:
    raise SystemExit(json.load(source)["format"] != "codi-ngspice-browser/1")
PY
then
    export CODI_RELINK_KLU=1
fi
CODI_NGSPICE_WORK="$target/work" CODI_EMSDK="$sdk" CODI_RELINK_OUTPUT="$target/relinked" bash "$target/app/test-relink.sh"
echo 'PASS independent extracted-directory relink. This is not a legal-completeness determination.'
