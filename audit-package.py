#!/usr/bin/env python3
"""Check a research package's inputs and binary binding; not a legal review."""
import argparse, base64, hashlib, io, json, pathlib, re, tarfile, zipfile

APP=pathlib.Path(__file__).resolve().parent
NG='ngspice-sf-mirror-ngspice-45.2'
EE='EEcircuit-engine-424c21eb9f9bb91e72c1befe2d7fc2f09641316c'
ARCHIVES={'ngspice.tar.gz':'3aa30022e975bc04e2d9566e62e76d15e108d7b887f520755383ba37464c2324','engine.tar.gz':'e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b'}
NOTICE_FILES=['ngspice-COPYING.txt','EEcircuit-engine-MIT.txt','numparam-README.txt','FreePDK-APACHE-LICENSE-2.0.txt','Emscripten-LICENSE.txt','musl-COPYRIGHT.txt','compiler-rt-LICENSE.txt','libunwind-LICENSE.txt','libcxx-LICENSE.txt','libcxxabi-LICENSE.txt','ATTRIBUTION.txt']+[f'SuiteSparse-{component}-{name}' for component in ['AMD','BTF','KLU','COLAMD'] for name in ['README.txt','Doc-lesser.txt']]+['SuiteSparse-AMD-Doc-License']
NOTICE_HASHES={
 'SuiteSparse-AMD-README.txt':'5c7984c35e4bb5c76002f2b98ef4942dd448771f64e95ecf3f12ee8503b1888e',
 'SuiteSparse-AMD-Doc-lesser.txt':'6095e9ffa777dd22839f7801aa845b31c9ed07f3d6bf8a26dc5d2dec8ccc0ef3',
 'SuiteSparse-AMD-Doc-License':'17dbc2fd3ad57076a70f2a8fc8c8ababc8adacfed2114c8d3f8e191972a4700d',
 'SuiteSparse-BTF-README.txt':'543637e056267a3e606bd2bf9a9ee0fe450c3396c8f49ea5eaac7b7587339746',
 'SuiteSparse-BTF-Doc-lesser.txt':'d1140673af4ac0a12a5c6dcbae3dfe49cf156b31218298bf740a4bdf0b4fc338',
 'SuiteSparse-KLU-README.txt':'56b4c99e8d75970f78da426f395b311142a705872ad5a6935257d8a0fe51903b',
 'SuiteSparse-KLU-Doc-lesser.txt':'6095e9ffa777dd22839f7801aa845b31c9ed07f3d6bf8a26dc5d2dec8ccc0ef3',
 'SuiteSparse-COLAMD-README.txt':'441bae341314a925813913c983c751b2be0cc89b3853666526a93baa18a82c4e',
 'SuiteSparse-COLAMD-Doc-lesser.txt':'6095e9ffa777dd22839f7801aa845b31c9ed07f3d6bf8a26dc5d2dec8ccc0ef3',
 'Emscripten-LICENSE.txt':'620a78084fc7ca97c0b5dea9abf891f3ffcadfdbf305276f099c9c4e12fc1d86',
 'musl-COPYRIGHT.txt':'f9bc4423732350eb0b3f7ed7e91d530298476f8fec0c6c427a1c04ade22655af',
 'compiler-rt-LICENSE.txt':'1a8f1058753f1ba890de984e48f0242a3a5c29a6a8f2ed9fd813f36985387e8d',
 'libunwind-LICENSE.txt':'b5efebcaca80879234098e52d1725e6d9eb8fb96a19fce625d39184b705f7b6d',
 'libcxx-LICENSE.txt':'539dd7aed86e8a4f12cbdd0e6c50c189c7d74847e4fecc64ce2c6ee3a01da38b',
 'libcxxabi-LICENSE.txt':'e2b35be49f7284a45b7baca8fc7b3ab7440e7902392b2528a457816b5bb2a15c',
}
REQUIRED=[f'work/{NG}/src/frontend/numparam/mystring.c',f'work/{NG}/src/maths/KLU/klu.c',f'work/{NG}/release/src/frontend/numparam/.libs/libnumparam.a',f'work/{NG}/release/src/maths/KLU/.libs/libKLU.a',f'work/{NG}/release/src/ngspice-main.o',f'work/{NG}/release/src/Makefile',f'work/{NG}/release/src/include/ngspice/config.h',f'work/{EE}/src/simulationLink.ts',f'work/{EE}/src/models/ptm.ts',f'work/{EE}/src/models/freepdk/freePDK.ts',f'work/{EE}/src/models/skywater/nfet18.ts',f'work/{EE}/src/models/gf180/gf180mos.ts',f'work/{EE}/Docker/pre.js',f'work/{EE}/package-lock.json','app/build-source.sh','app/test-relink.sh','app/verify-portable.sh','app/audit-package.py','app/prepare-models.py','app/MODELS.md']
SHA=lambda data:hashlib.sha256(data).hexdigest()
WASM_URL=re.compile(rb'data:application/wasm;base64,([A-Za-z0-9+/]+={0,2})')

def wasm_bindings(data,expected):
    matches=WASM_URL.findall(data)
    if not matches:raise ValueError('No embedded WASM found in engine')
    for encoded in matches:
        try:binary=base64.b64decode(encoded,validate=True)
        except ValueError as exc:raise ValueError('Invalid embedded WASM') from exc
        if SHA(binary)!=expected:raise ValueError('Embedded WASM does not match the packaged build')
    return len(matches)

def audit(archive,engine,notices,worker=None,home=None):
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist();names=[e.filename for e in entries]
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive entry')
        if len(entries)>20000 or sum(e.file_size for e in entries)>1024*1024*1024:raise ValueError('Archive exceeds audit limits')
        for entry in entries:
            name=entry.filename;p=pathlib.PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or not p.parts or entry.file_size>256*1024*1024:raise ValueError('Unsafe archive entry: '+name)
            if any(x in {'account-data','account-state','issuer','.ssh','node_modules'} for x in p.parts) or p.suffix.lower() in {'.sqlite','.sqlite3','.db','.pem','.key'}:raise ValueError('Private or generated dependency entry: '+name)
        present=set(names)
        for name in REQUIRED+['notices/'+n for n in NOTICE_FILES]+['package.json']:
            if name not in present:raise ValueError('Missing required source, object or notice: '+name)
        meta=json.loads(z.read('package.json'))
        if meta.get('format')!='codi-ngspice-research/1' or meta.get('ngspice')!=NG or meta.get('engine')!=EE or meta.get('archives')!=ARCHIVES:raise ValueError('Unexpected source provenance metadata')
        if meta.get('workPathToken')!='@CODI_WORK@' or meta.get('sdkPathToken')!='@CODI_EMSDK@':raise ValueError('Unexpected relocation tokens')
        if meta.get('clangSha256')!='5fc2a956e0b2aa53ac73c9fffbfcd73a608a141eca4155682b6ce10c448f6053' or meta.get('wasmLdSha256')!='605f1231476d92e2abae151c47ff0192d3e84c9d115038d481a4d71e8d110db5':raise ValueError('Unexpected toolchain hashes')
        if meta.get('suiteSparseNoticeArchiveSha256')!='3340ec0508d0680451bcc7d7581d04942c58b07cc71dfb7e13d0718060c911d9':raise ValueError('Unexpected SuiteSparse provenance')
        if meta.get('engineOriginalArchiveSha256')!='e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b':raise ValueError('Unexpected wrapper provenance')
        if meta.get('modelLicenses')!='unreviewed':raise ValueError('Model licensing status must remain unreviewed')
        for name,digest in ARCHIVES.items():
            if SHA(z.read('work/'+name))!=digest:raise ValueError('Source archive hash mismatch: '+name)
        for archive_name,files in [('ngspice.tar.gz',[(f'{NG}/COPYING','ngspice-COPYING.txt'),(f'{NG}/src/frontend/numparam/readme.txt','numparam-README.txt')]),('engine.tar.gz',[(f'{EE}/LICENSE','EEcircuit-engine-MIT.txt'),(f'{EE}/src/models/freepdk/APACHE-LICENSE-2.0.txt','FreePDK-APACHE-LICENSE-2.0.txt')])]:
            with tarfile.open(fileobj=io.BytesIO(z.read('work/'+archive_name)),mode='r:gz') as original:
                for member,notice in files:
                    source=original.extractfile(member)
                    if source is None or source.read()!=z.read('notices/'+notice):raise ValueError('Notice differs from pinned source: '+notice)
                if archive_name=='engine.tar.gz':
                    source_models={m.name for m in original.getmembers() if m.isfile() and (m.name.startswith(f'{EE}/src/models/') or m.name==f'{EE}/src/circuits.ts')}
                    packaged_models={n[5:] for n in names if n.startswith(f'work/{EE}/src/models/') or n==f'work/{EE}/src/circuits.ts'}
                    if not source_models or source_models!=packaged_models:raise ValueError('Packaged model source set differs from upstream')
                    for member in source_models:
                        source=original.extractfile(member)
                        if source is None or source.read()!=z.read('work/'+member):raise ValueError('Model source differs from upstream: '+member)
        for name,digest in NOTICE_HASHES.items():
            if SHA(z.read('notices/'+name))!=digest:raise ValueError('Notice differs from pinned source: '+name)
        attribution=z.read('notices/ATTRIBUTION.txt')
        if b'Used by permission' not in attribution or b'Timothy A. Davis' not in attribution:raise ValueError('AMD attribution missing')
        wasm=z.read(f'work/{NG}/release/src/spice.wasm');wrapper=z.read(f'work/{EE}/dist/eecircuit-engine.mjs')
        patched=z.read(f'work/{EE}/src/simulationLink.ts')
        if b'from "./models/' in patched or b'module.FS?.writeFile("/modelcard.' in patched:raise ValueError('Unexpected model integration change; update the audit and licensing review')
        if SHA(wasm)!=meta['wasmSha256'] or SHA(wrapper)!=meta['wrapperSha256']:raise ValueError('Packaged build hash mismatch')
        if SHA(pathlib.Path(engine).read_bytes())!=meta['wrapperSha256']:raise ValueError('Installed engine differs from source package')
        count=wasm_bindings(wrapper,meta['wasmSha256'])
        config=z.read(f'work/{NG}/release/src/include/ngspice/config.h')
        for enabled in [b'#define KLU']:
            if enabled not in config:raise ValueError('Unexpected build component configuration')
        for disabled in [b'/* #undef XSPICE */',b'/* #undef OSDI */',b'/* #undef CIDER */']:
            if disabled not in config:raise ValueError('Unexpected build component configuration')
        package_notices=sorted(n for n in names if n.startswith('notices/') and not n.endswith('/'))
        expected='\n'.join('\n===== '+n+' =====\n'+z.read(n).decode('utf-8',errors='replace') for n in package_notices)
        if pathlib.Path(notices).read_text(encoding='utf-8')!=expected:raise ValueError('Served notices do not match the source package')
        home_bytes=(str(home or pathlib.Path.home())+'/').encode()
        for entry in entries:
            if home_bytes in z.read(entry):raise ValueError('Workstation home path found: '+entry.filename)
        if worker is not None:wasm_bindings(pathlib.Path(worker).read_bytes(),meta['wasmSha256'])
        return {'archiveSHA256':SHA(pathlib.Path(archive).read_bytes()),'wasmSHA256':meta['wasmSha256'],'wrapperSHA256':meta['wrapperSha256'],'noticeFiles':len(package_notices),'embeddedCopies':count,'workerChecked':worker is not None}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=pathlib.Path,default=APP/'node_modules/codi-ngspice/source-relink.zip')
    parser.add_argument('--engine',type=pathlib.Path,default=APP/'node_modules/codi-ngspice/dist/eecircuit-engine.mjs')
    parser.add_argument('--notices',type=pathlib.Path,default=APP/'node_modules/codi-ngspice/NOTICES.txt')
    parser.add_argument('--worker',type=pathlib.Path,help='Also verify the actual app-builder worker bundle')
    args=parser.parse_args();print(json.dumps(audit(args.archive,args.engine,args.notices,args.worker),indent=2));print('PASS technical package audit; distribution review is still required.')

if __name__=='__main__':main()
