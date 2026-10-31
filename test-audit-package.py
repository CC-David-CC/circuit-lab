#!/usr/bin/env python3
"""Meaningful negative checks for the source and binary release gate."""
import base64, importlib.util, io, json, pathlib, tarfile, tempfile, unittest, zipfile

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('codi_ngspice_audit',HERE/'audit-package.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def source_tar(files):
    result=io.BytesIO()
    with tarfile.open(fileobj=result,mode='w:gz') as t:
        for name,data in files.items():
            item=tarfile.TarInfo(name);item.size=len(data);t.addfile(item,io.BytesIO(data))
    return result.getvalue()

class PackageAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.original_archives=audit.ARCHIVES;self.original_hashes=audit.NOTICE_HASHES
        self.ng=source_tar({f'{audit.NG}/COPYING':b'NG LICENSE',f'{audit.NG}/src/frontend/numparam/readme.txt':b'NUMPARAM LICENSE'})
        self.model_files={f'{audit.EE}/src/models/ptm.ts':b'PTM',f'{audit.EE}/src/models/freepdk/freePDK.ts':b'PDK',f'{audit.EE}/src/models/skywater/nfet18.ts':b'SKY',f'{audit.EE}/src/models/gf180/gf180mos.ts':b'GF',f'{audit.EE}/src/models/freepdk/APACHE-LICENSE-2.0.txt':b'APACHE LICENSE',f'{audit.EE}/src/circuits.ts':b'EXAMPLES'};self.ee=source_tar({f'{audit.EE}/LICENSE':b'WRAPPER LICENSE',**self.model_files})
        audit.ARCHIVES={'ngspice.tar.gz':audit.SHA(self.ng),'engine.tar.gz':audit.SHA(self.ee)}
        self.notices={n:('notice '+n).encode() for n in audit.NOTICE_FILES}
        self.notices.update({'ngspice-COPYING.txt':b'NG LICENSE','numparam-README.txt':b'NUMPARAM LICENSE','EEcircuit-engine-MIT.txt':b'WRAPPER LICENSE','FreePDK-APACHE-LICENSE-2.0.txt':b'APACHE LICENSE','ATTRIBUTION.txt':b'Timothy A. Davis - Used by permission'})
        audit.NOTICE_HASHES={n:audit.SHA(self.notices[n]) for n in self.original_hashes}
        self.wasm=b'\x00asm\x01\x00\x00\x00fixture';self.wrapper=b'const wasm="data:application/wasm;base64,'+base64.b64encode(self.wasm)+b'";'
    def tearDown(self):
        audit.ARCHIVES=self.original_archives;audit.NOTICE_HASHES=self.original_hashes;self.tmp.cleanup()
    def create(self, *, missing=None, bad_notice=False, wrong_embedded=False, private=False, wrong_worker=False, modified_model=False):
        values={n:b'object or source' for n in audit.REQUIRED}
        values.update({'work/ngspice.tar.gz':self.ng,'work/engine.tar.gz':self.ee})
        values.update({'work/'+n:data for n,data in self.model_files.items()})
        notices=dict(self.notices)
        if bad_notice:notices['SuiteSparse-AMD-README.txt']=b'modified notice'
        for n,data in notices.items():values['notices/'+n]=data
        config=b'#define KLU\n/* #undef XSPICE */\n/* #undef OSDI */\n/* #undef CIDER */\n'
        values[f'work/{audit.NG}/release/src/include/ngspice/config.h']=config
        wasm=self.wasm;wrapper=self.wrapper
        if wrong_embedded:wrapper=b'"data:application/wasm;base64,'+base64.b64encode(b'different wasm')+b'"'
        values[f'work/{audit.NG}/release/src/spice.wasm']=wasm
        values[f'work/{audit.EE}/dist/eecircuit-engine.mjs']=wrapper
        meta={'format':'codi-ngspice-research/1','ngspice':audit.NG,'engine':audit.EE,'archives':audit.ARCHIVES,'workPathToken':'@CODI_WORK@','sdkPathToken':'@CODI_EMSDK@','wasmSha256':audit.SHA(wasm),'wrapperSha256':audit.SHA(wrapper),'clangSha256':'5fc2a956e0b2aa53ac73c9fffbfcd73a608a141eca4155682b6ce10c448f6053','wasmLdSha256':'605f1231476d92e2abae151c47ff0192d3e84c9d115038d481a4d71e8d110db5','modelLicenses':'unreviewed','engineOriginalArchiveSha256':'e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b','suiteSparseNoticeArchiveSha256':'3340ec0508d0680451bcc7d7581d04942c58b07cc71dfb7e13d0718060c911d9'}
        values['package.json']=json.dumps(meta).encode()
        if private:values['work/account-data/test.db']=b'private'
        if modified_model:values[f'work/{audit.EE}/src/models/ptm.ts']=b'modified PTM data'
        if missing:values.pop(missing)
        archive=self.root/'source.zip';engine=self.root/'engine.mjs';noticefile=self.root/'NOTICES.txt';worker=self.root/'worker.mjs'
        with zipfile.ZipFile(archive,'w') as z:
            for n,data in values.items():z.writestr(n,data)
        engine.write_bytes(wrapper)
        ordered=sorted(n for n in values if n.startswith('notices/'))
        noticefile.write_text('\n'.join('\n===== '+n+' =====\n'+values[n].decode() for n in ordered))
        worker.write_bytes(b'"data:application/wasm;base64,'+base64.b64encode(b'other' if wrong_worker else wasm)+b'"')
        return archive,engine,noticefile,worker
    def test_valid_bound_package(self):
        result=audit.audit(*self.create(),home='/fakehome');self.assertEqual(result['noticeFiles'],20);self.assertTrue(result['workerChecked'])
    def test_wrong_embedded_binary_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Embedded WASM'):audit.audit(*self.create(wrong_embedded=True),home='/fakehome')
    def test_wrong_bundled_worker_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Embedded WASM'):audit.audit(*self.create(wrong_worker=True),home='/fakehome')
    def test_missing_linkable_object_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing required'):audit.audit(*self.create(missing=audit.REQUIRED[2]),home='/fakehome')
    def test_modified_notice_is_rejected_even_if_served_text_matches(self):
        with self.assertRaisesRegex(ValueError,'Notice differs'):audit.audit(*self.create(bad_notice=True),home='/fakehome')
    def test_private_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Private or generated'):audit.audit(*self.create(private=True),home='/fakehome')
    def test_missing_model_source_is_rejected(self):
        missing=f'work/{audit.EE}/src/models/ptm.ts'
        with self.assertRaisesRegex(ValueError,'Missing required'):audit.audit(*self.create(missing=missing),home='/fakehome')
    def test_modified_model_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Model source differs'):audit.audit(*self.create(modified_model=True),home='/fakehome')

if __name__=='__main__':unittest.main()
