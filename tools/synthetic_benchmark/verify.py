"""Check synthetic pilot completeness, budgets, source digest, and raw scores."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import benchmark as m

def verify(root):
    summary=json.loads((root/'summary.json').read_text())
    if summary['source_sha256']!=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest():
        raise ValueError('benchmark source digest mismatch')
    n=summary['blocks']
    if type(n)!=int or not 2<=n<=100:raise ValueError('invalid block count')
    tasks=m.generate(n)
    oracle={(t['block'],t['kind']):m.oracle(t) for t in tasks}
    lookup={(t['block'],t['kind']):t for t in tasks}
    rows=json.loads((root/'records.json').read_text())
    expected={(t['block'],t['kind'],k) for t in tasks for k in m.LAYERS}
    keys=[(r['block'],r['kind'],r['condition']) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=expected:raise ValueError('incomplete or duplicate records')
    for r in rows:
        key=(r['block'],r['kind'])
        if r['execution_status']!='OK':raise ValueError('execution failure retained in pilot')
        if not 0<=r['candidate_evaluations']<=100:raise ValueError('candidate budget exceeded')
        if r['cpu_seconds']<0 or r['cpu_seconds']>4 or r['wall_seconds']<0 or r['wall_seconds']>6:
            raise ValueError('resource measurement outside development limits')
        scored=m.score(lookup[key],oracle[key],r['submission'])
        if any(r[k]!=v for k,v in scored.items()):raise ValueError('recorded score mismatch')
    scores={k:statistics.mean(r['justified'] for r in rows if r['condition']==k) for k in m.LAYERS}
    if scores!=summary['scores']:raise ValueError('summary score mismatch')
    return {'status':'VERIFIED_DEVELOPMENT_RECORDS','executions':len(rows),
            'independent_replication':False,'production_authorized':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
    print(json.dumps(verify(p.parse_args().directory),indent=2))
