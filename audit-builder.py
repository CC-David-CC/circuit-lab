#!/usr/bin/env python3
"""Verify the actual app-builder bundle against its source/relink package."""
import argparse, hashlib, json, pathlib, re, runpy
APP=pathlib.Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=pathlib.Path,help='App-builder output directory containing apps.json')
    parser.add_argument('--app-id',default='circuit-lab',help='Use arduino-simulator only for the isolated test alias')
    args=parser.parse_args();root=args.output.resolve()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',args.app_id):raise ValueError('Invalid app id')
    catalog=json.loads((root/'apps.json').read_text());matches=[a for a in catalog.get('apps',[]) if a.get('id')==args.app_id]
    if len(matches)!=1:raise ValueError('Expected one matching app in catalog')
    record=matches[0];sha=record.get('bundleSHA256','')
    if not re.fullmatch('[a-f0-9]{64}',sha):raise ValueError('Invalid bundle identifier')
    bundle=root/'apps'/args.app_id/sha
    paths=['index.mjs','workers/spice.mjs','node_modules/codi-ngspice/source-relink.zip','node_modules/codi-ngspice/NOTICES.txt']
    for name in paths:
        path=bundle/name
        if path.is_symlink() or not path.is_file():raise ValueError('Missing or linked bundle file: '+name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record.get('files',{}).get(name,{}).get('sha256'):raise ValueError('Bundle/catalog hash mismatch: '+name)
    auditor=runpy.run_path(str(APP/'audit-package.py'))['audit']
    result=auditor(bundle/paths[2],APP/'node_modules/codi-ngspice/dist/eecircuit-engine.mjs',bundle/paths[3],bundle/paths[1])
    print(json.dumps(result,indent=2));print('PASS built worker, source package, notices and catalog agree; distribution review remains required.')

if __name__=='__main__':main()
