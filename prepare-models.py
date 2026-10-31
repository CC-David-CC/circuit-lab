#!/usr/bin/env python3
"""Preserve the pinned upstream model sources for local development only."""
import argparse,hashlib,io,json,pathlib,tarfile,urllib.request

APP=pathlib.Path(__file__).resolve().parent
REV='424c21eb9f9bb91e72c1befe2d7fc2f09641316c'
SHA='e847152a73df19d7a3ece07cd60c63ec7e47e038d2dd615d5dd5cce0515e8d6b'
URL='https://codeload.github.com/eelab-dev/EEcircuit-engine/tar.gz/'+REV
PREFIX='EEcircuit-engine-'+REV+'/'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=pathlib.Path,help='Optional already-downloaded pinned upstream archive')
    ap.add_argument('--output',type=pathlib.Path,default=APP/'.build/model-source',help='Fresh local development directory; never overwrites existing files')
    args=ap.parse_args();out=args.output.resolve()
    if out.exists():raise RuntimeError('Output exists; preserving it. Choose a fresh directory.')
    if args.archive:raw=args.archive.read_bytes()
    else:
        with urllib.request.urlopen(URL,timeout=60) as response:raw=response.read(50*1024*1024+1)
    if len(raw)>50*1024*1024 or hashlib.sha256(raw).hexdigest()!=SHA:raise RuntimeError('Upstream archive hash mismatch')
    selected={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as source:
        for item in source.getmembers():
            if not item.isfile() or not item.name.startswith(PREFIX):continue
            relative=pathlib.PurePosixPath(item.name[len(PREFIX):])
            if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('Unsafe source path')
            if relative.as_posix() not in {'LICENSE','src/circuits.ts'} and relative.parts[:2]!=('src','models'):continue
            if item.size>10*1024*1024:raise RuntimeError('Model file exceeds size limit')
            if relative.as_posix() in selected:raise RuntimeError('Duplicate model source')
            f=source.extractfile(item)
            if f is None:raise RuntimeError('Cannot read model source')
            selected[relative.as_posix()]=f.read()
    if 'src/models/ptm.ts' not in selected or not any(x.startswith('src/models/skywater/') for x in selected):raise RuntimeError('Pinned model data is incomplete')
    out.mkdir(parents=True)
    for name,data in selected.items():
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (out/'PROVENANCE.json').write_text(json.dumps({'upstream':URL,'revision':REV,'archiveSHA256':SHA,'scope':'Local development; redistribution terms require review','files':{n:hashlib.sha256(data).hexdigest() for n,data in sorted(selected.items())}},indent=2)+'\n')
    print('Preserved',len(selected),'upstream model/example source files in',out)
    print('Local development only; see MODELS.md before distribution.')

if __name__=='__main__':main()
