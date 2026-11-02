"""Exploratory B6 module ablations on the same public synthetic worlds."""
import json
from pathlib import Path
import statistics
import sys
import argparse
import benchmark as m
from runner import run

if len(sys.argv)>1 and sys.argv[1]=='adapter':
    m.LAYERS['B6']=m.LAYERS['B6']-{sys.argv[2]}
    print(json.dumps(m.participant(json.load(sys.stdin),'B6')))
else:
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--blocks',type=int,default=30)
    args=parser.parse_args()
    if not 2<=args.blocks<=100:parser.error('blocks must be between 2 and 100')
    root=args.output;root.mkdir(parents=True,exist_ok=False)
    rows=[]
    for t in m.generate(args.blocks):
        o=m.oracle(t)
        for removed in ('structure','time','utility','evidence'):
            r=run([sys.executable,str(Path(__file__).resolve()),'adapter',removed],t,wall=5,cpu=3)
            s=r['submission'] if r['status']=='OK' else {'decision':'FAILURE','evaluations':0}
            rows.append({'block':t['block'],'kind':t['kind'],'removed':removed,
                         'execution_status':r['status'],'candidate_evaluations':s['evaluations'],
                         'cpu_seconds':r['cpu_seconds'],**m.score(t,o,s)})
    (root/'records.json').write_text(json.dumps(rows,indent=2)+'\n')
    summary={k:statistics.mean(x['justified'] for x in rows if x['removed']==k)
             for k in ('structure','time','utility','evidence')}
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
