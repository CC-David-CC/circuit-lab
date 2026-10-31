#!/usr/bin/env python3
"""Create a research-only source/relink bundle from a completed pinned build."""
import argparse, hashlib, json, os, pathlib, runpy, tarfile, zipfile

APP = pathlib.Path(__file__).resolve().parent
ROOT = APP.parents[2]
NG = 'ngspice-sf-mirror-ngspice-45.2'
EE = 'EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c'
ORIGINAL_ENGINE_SHA='e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b'
EXPECTED = {'ngspice.tar.gz':'3aa30022e975bc04e2d9566e62e76d15e108d7b887f520755383ba37464c2324','engine.tar.gz':ORIGINAL_ENGINE_SHA}
SUITESPARSE_SHA = '3340ec0508d0680451bcc7d7581d04942c58b07cc71dfb7e13d0718060c911d9'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--work',type=pathlib.Path,default=ROOT/'.build/circuit-lab-source')
    ap.add_argument('--sdk',type=pathlib.Path,default=ROOT/'.build/ngspice-emsdk')
    ap.add_argument('--suitesparse',type=pathlib.Path,default=ROOT/'.build/suitesparse-3.7.0.tar.gz')
    ap.add_argument('--output',type=pathlib.Path,required=True)
    ap.add_argument('--research-allow-unreviewed-models',action='store_true',help='Create a local research-only archive containing model data with unresolved redistribution terms')
    args=ap.parse_args();work=args.work.resolve();sdk=args.sdk.resolve();out=args.output.resolve()
    if not args.research_allow_unreviewed_models:raise RuntimeError('Model redistribution review is unresolved; only explicitly requested local research packaging is permitted')
    raw_engine=(work/'engine.tar.gz').read_bytes()
    if hashlib.sha256(raw_engine).hexdigest()!=ORIGINAL_ENGINE_SHA:raise RuntimeError('Original wrapper source archive hash mismatch')
    sources={name:work/name for name in EXPECTED}
    for name,digest in EXPECTED.items():
        if hashlib.sha256(sources[name].read_bytes()).hexdigest()!=digest: raise RuntimeError('source archive hash mismatch: '+name)
    suite=args.suitesparse.resolve()
    if hashlib.sha256(suite.read_bytes()).hexdigest()!=SUITESPARSE_SHA:raise RuntimeError('SuiteSparse notice archive hash mismatch')
    if not (work/NG/'release/src/spice.wasm').is_file() or not (work/EE/'dist/eecircuit-engine.mjs').is_file():raise RuntimeError('Build must finish before packaging')
    installed=APP/'node_modules/codi-ngspice/dist/eecircuit-engine.mjs'
    if not installed.is_file() or hashlib.sha256(installed.read_bytes()).digest()!=hashlib.sha256((work/EE/'dist/eecircuit-engine.mjs').read_bytes()).digest():
        raise RuntimeError('Installed engine does not match the source/relink build; rebuild or restore it before packaging')
    files={}
    def put(name,path):
        if name in files: raise RuntimeError('duplicate package path: '+name)
        parts=path.relative_to(work).parts if path.is_relative_to(work) else ()
        if any(part in {'account-data','account-state','issuer','.ssh'} for part in parts) or path.suffix.lower() in {'.sqlite','.sqlite3','.db','.pem','.key'} or path.name.startswith('.env'):
            raise RuntimeError('Refusing private-state or key-like package input: '+name)
        files[name]=path
    for name in EXPECTED:put('work/'+name,sources[name])
    for tree in [NG,EE]:
        for p in sorted((work/tree).rglob('*')):
            if not p.is_file() or p.name=='config.log' or any(s in {'node_modules','.git','autom4te.cache','.deps'} for s in p.relative_to(work/tree).parts):continue
            put('work/'+p.relative_to(work).as_posix(),p)
    for name in ['README.md','MODELS.md','package.json','package-lock.json','index.mjs','style.css','app.json','netlist.mjs','worker.mjs','test-netlist.mjs','build-source.sh','test-relink.sh','package-source.py','verify-portable.sh','audit-package.py','audit-builder.py','test-audit-package.py','prepare-models.py']:
        p=APP/name
        if p.exists():put('app/'+name,p)
    browser_test=ROOT/'tests/circuit-account-browser.test.mjs'
    if browser_test.is_file():put('app/tests/circuit-account-browser.test.mjs',browser_test)
    notices={
      'ngspice-COPYING.txt':work/NG/'COPYING',
      'EEcircuit-engine-MIT.txt':work/EE/'LICENSE',
      'numparam-README.txt':work/NG/'src/frontend/numparam/readme.txt',
      'FreePDK-APACHE-LICENSE-2.0.txt':work/EE/'src/models/freepdk/APACHE-LICENSE-2.0.txt',
      'Emscripten-LICENSE.txt':sdk/'upstream/emscripten/LICENSE',
      'musl-COPYRIGHT.txt':sdk/'upstream/emscripten/system/lib/libc/musl/COPYRIGHT',
      'compiler-rt-LICENSE.txt':sdk/'upstream/emscripten/system/lib/compiler-rt/LICENSE.TXT',
      'libunwind-LICENSE.txt':sdk/'upstream/emscripten/system/lib/libunwind/LICENSE.TXT',
      'libcxx-LICENSE.txt':sdk/'upstream/emscripten/system/lib/libcxx/LICENSE.TXT',
      'libcxxabi-LICENSE.txt':sdk/'upstream/emscripten/system/lib/libcxxabi/LICENSE.TXT',
    }
    for name,p in notices.items():
        if not p.is_file():raise RuntimeError('missing toolchain notice: '+str(p))
        put('notices/'+name,p)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(sdk/'upstream/bin/clang')!='5fc2a956e0b2aa53ac73c9fffbfcd73a608a141eca4155682b6ce10c448f6053' or digest(sdk/'upstream/bin/wasm-ld')!='605f1231476d92e2abae151c47ff0192d3e84c9d115038d481a4d71e8d110db5':
        raise RuntimeError('SDK executable hashes do not match the pinned build')
    metadata={'format':'codi-ngspice-research/1','workPathToken':'@CODI_WORK@','sdkPathToken':'@CODI_EMSDK@','ngspice':NG,'engine':EE,'archives':EXPECTED,
      'wasmSha256':digest(work/NG/'release/src/spice.wasm'),
      'wrapperSha256':digest(work/EE/'dist/eecircuit-engine.mjs'),
      'clangSha256':digest(sdk/'upstream/bin/clang'),
      'wasmLdSha256':digest(sdk/'upstream/bin/wasm-ld'),
      'suiteSparseNoticeArchiveSha256':SUITESPARSE_SHA,
      'engineOriginalArchiveSha256':ORIGINAL_ENGINE_SHA,
      'modelLicenses':'unreviewed',
      'warning':'Research only: legal completeness and clean-room reproducibility are not established.'}
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        def add(name,data,mode=0o644):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(0o100000|mode)<<16;z.writestr(info,data)
        add('package.json',json.dumps(metadata,sort_keys=True,indent=2).encode()+b'\n')
        for name,path in sorted(files.items()):
            data=path.read_bytes()
            if name.startswith('work/'+NG+'/release/') and b'\0' not in data:
                data=data.replace(str(work).encode(),b'@CODI_WORK@').replace(str(sdk).encode(),b'@CODI_EMSDK@')
            if str(pathlib.Path.home()).encode()+b'/' in data:
                raise RuntimeError('Local home path present in package input: '+name)
            add(name,data,0o755 if os.access(path,os.X_OK) else 0o644)
        # ngspice imports these SuiteSparse 3.7.0 sources but its KLU directory
        # references upstream README files that are not copied into ngspice.
        with tarfile.open(suite) as original:
            for component in ['AMD','BTF','KLU','COLAMD']:
                for relative in ['README.txt','Doc/lesser.txt'] + (['Doc/License'] if component=='AMD' else []):
                    member=f'SuiteSparse/{component}/{relative}'
                    stream=original.extractfile(member)
                    if stream is None:raise RuntimeError('missing SuiteSparse notice '+member)
                    add(f'notices/SuiteSparse-{component}-{relative.replace("/","-")}',stream.read())
        add('notices/ATTRIBUTION.txt',('AMD, Copyright (c) 2009-2011 Timothy A. Davis, Patrick R. Amestoy, and Iain S. Duff.\n'
          'Available from https://people.engr.tamu.edu/davis/SuiteSparse/SuiteSparse-3.7.0.tar.gz.\n'
          'Used by permission. The version incorporated into ngspice has been modified.\n'
          'See the included SuiteSparse AMD, BTF, KLU and COLAMD notices and ngspice COPYING for details.\n').encode())
    print(f'Packaged {len(files)} files, {out.stat().st_size} bytes: {out}')
    print('SHA-256',hashlib.sha256(out.read_bytes()).hexdigest())
    with zipfile.ZipFile(out) as z:
        names=sorted(n for n in z.namelist() if n.startswith('notices/') and not n.endswith('/'))
        notices='\n'.join('\n===== '+name+' =====\n'+z.read(name).decode('utf-8',errors='replace') for name in names)
    notice_path=out.parent/'NOTICES.txt'
    notice_path.write_text(notices,encoding='utf-8')
    try:
        auditor=runpy.run_path(str(APP/'audit-package.py'))['audit']
        auditor(out,installed,notice_path)
    except Exception:
        out.unlink(missing_ok=True)
        notice_path.unlink(missing_ok=True)
        raise
    print('PASS technical package audit; final distribution review remains required.')

if __name__=='__main__':main()
