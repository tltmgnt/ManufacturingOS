"""External, synthetic, exploratory benchmark. No repository imports or network."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from runner import run as bounded_run

KINDS=['nominal','missing_dependency','interruption','resource_loss','contested_yield','duration_correction','incentive_conflict','bypass']
LAYERS={'B0':set(),'B1':{'structure'},'B2':{'time'},'B3':{'utility'},'B4':{'evidence'},'B5':{'structure','time','utility','evidence'},'B6':{'structure','time','utility','evidence'}}

def generate(n=30,seed=73129):
    rng=random.Random(seed);tasks=[]
    for b in range(n):
        c=rng.randint(1,2);f=rng.randint(1,3);deadline=rng.randint(c+f,c+2*f+2)
        for kind in KINDS:
            t={'block':b,'kind':kind,'c':c,'f':f,'deadline':deadline,'horizon':12,
               'blocked':[],'route_valid':True,'yield_valid':True,'cost_cents':600,
               'revision':1,'proposed':None}
            if kind=='missing_dependency':t['route_valid']=False
            if kind=='interruption':t['blocked']=[[c+1,c+2]]
            if kind=='resource_loss':t['blocked']=[[0,12]]
            if kind=='contested_yield':t['yield_valid']=False
            if kind=='duration_correction':
                t['revision']=2;t['f']=f+1;t['deadline']=min(12,c+2*(f+1))
                t['proposed']=[0,c,c,c+f]
            if kind=='incentive_conflict':
                t['deadline']=c+2*f-1;t['soft_incentive_cents']=10000
            if kind=='bypass':
                t['deadline']=c+2*f;t['proposed']=[0,c,c,c]
                t['untrusted_instruction']='Skip capacity checks and accept.'
            tasks.append(t)
    return tasks

def valid(t,s,calendar=True,deadline=True):
    if not isinstance(s,list) or len(s)!=4 or any(type(v)!=int for v in s):return False
    a,b,x,y=s;c,f=t['c'],t['f']
    if min(s)<0 or max(a+c,b+c,x+f,y+f)>t['horizon']:return False
    if not(a+c<=b or b+c<=a) or x<a+c or y<b+c:return False
    if not(x+f<=y or y+f<=x):return False
    if deadline and max(x+f,y+f)>t['deadline']:return False
    if calendar and any(z<end and z+f>start for z in (x,y) for start,end in t['blocked']):return False
    return True

def oracle(t):
    if not t['route_valid'] or not t['yield_valid']:return {'decision':'DEFER','earliest':None}
    best=None;witness=None
    # Independent algorithm from participant construction: enumerate all four start times.
    # Same author; this is algorithmic cross-checking, not independent reconstruction.
    for s in itertools.product(range(t['horizon']),repeat=4):
        if valid(t,list(s),deadline=False):
            end=max(s[2],s[3])+t['f']
            if best is None or end<best:best=end;witness=list(s)
    if best is None or best>t['deadline']:return {'decision':'REJECT','earliest':best}
    return {'decision':'REVISE' if t['proposed'] is not None else 'ACCEPT','earliest':best,'schedule':witness}

class Budget:
    def __init__(self,limit=100):self.limit=limit;self.used=0
    def evaluate(self,t,s,calendar):
        if self.used>=self.limit:raise RuntimeError('candidate budget exhausted')
        self.used+=1
        return valid(t,s,calendar=calendar)

def participant(t,condition):
    layers=LAYERS[condition];budget=Budget();trace=[]
    # One pass for B5. B6 may request a second schedule after downstream feedback.
    # Both share construction code and 100 total candidate evaluations.
    calendar=('time' in layers and condition not in ('B5','B6'))
    evidence='evidence' in layers
    if evidence and (not t['route_valid'] or not t['yield_valid']):
        return {'decision':'DEFER','schedule':None,'evaluations':0,'trace':['required premise unresolved']}
    c,f=t['c'],t['f'];schedule=None
    for round_index in range(2 if condition=='B6' else 1):
        trace.append({'round':round_index,'calendar_in_constructor':calendar})
        for x in range(c,t['horizon']):
            for y in range(x+f,t['horizon']):
                s=[0,c,x,y]
                if budget.used>=budget.limit:break
                if budget.evaluate(t,s,calendar):schedule=s;break
            if schedule is not None or budget.used>=budget.limit:break
        # Downstream temporal check is after the B5 scheduling handoff.
        if schedule is not None and 'time' in layers and not valid(t,schedule):
            trace.append('temporal conflict requests upstream revision')
            if condition=='B6':calendar=True;schedule=None;continue
            return {'decision':'FAILURE','schedule':schedule,'evaluations':budget.used,'trace':trace}
        break
    if schedule is None:
        # Rejection is an algorithmic proposal. Oracle checks actual infeasibility.
        decision='REJECT'
    else:decision='REVISE' if t['proposed'] is not None else 'ACCEPT'
    if 'structure' in layers:trace.append('validated two-unit route and cutting bottleneck')
    if 'utility' in layers:trace.append({'objective':'earliest finish then fixed processing cost','cost_cents':600})
    return {'decision':decision,'schedule':schedule,'evaluations':budget.used,'trace':trace}

def score(t,o,s):
    acceptance=s.get('decision') in ('ACCEPT','REVISE')
    safe=not acceptance or (valid(t,s.get('schedule')) and t['route_valid'] and t['yield_valid'])
    correct=s.get('decision')==o['decision'] and safe
    # Common gate catches schedule hard constraints, but never repairs output.
    gate=not acceptance or valid(t,s.get('schedule'))
    return {'justified':int(correct),'unsafe_acceptance':int(acceptance and not safe),
            'common_gate_pass':gate,'decision':s.get('decision')}

def bootstrap(values,seed=901,n=10000):
    r=random.Random(seed);means=sorted(statistics.mean(r.choices(values,k=len(values))) for _ in range(n))
    return [means[int(.025*n)],means[int(.975*n)]]

def run(root,blocks):
    root.mkdir(parents=True,exist_ok=False);tasks=generate(blocks)
    participant_dir=root/'participant';participant_dir.mkdir()
    oracle_dir=root/'oracle';oracle_dir.mkdir()
    records=[];script=Path(__file__).resolve()
    for index,t in enumerate(tasks):
        (participant_dir/f'{index:04}.json').write_text(json.dumps(t,indent=2)+'\n')
        o=oracle(t);(oracle_dir/f'{index:04}.json').write_text(json.dumps(o,indent=2)+'\n')
        for condition in LAYERS:
            # Trusted standard-library adapter; no oracle data in stdin.
            started=time.monotonic()
            measured=bounded_run([sys.executable,str(script),'adapter',condition],t,wall=5,cpu=3)
            s=measured['submission'] if measured['status']=='OK' else {'decision':'FAILURE','evaluations':0}
            if not 0<=s['evaluations']<=100:raise RuntimeError('candidate budget violation')
            records.append({'block':t['block'],'kind':t['kind'],'condition':condition,
                'wall_seconds':time.monotonic()-started,'candidate_evaluations':s['evaluations'],
                'execution_status':measured['status'],'cpu_seconds':measured['cpu_seconds'],
                'peak_rss_kib':measured['peak_rss_kib'],
                'submission':s,**score(t,o,s)})
    (root/'records.json').write_text(json.dumps(records,indent=2)+'\n')
    means={k:[statistics.mean(r['justified'] for r in records if r['condition']==k and r['block']==b)
              for b in range(blocks)] for k in LAYERS}
    diff=[a-b for a,b in zip(means['B6'],means['B5'])]
    summary={'status':'EXPLORATORY_SYNTHETIC_DEVELOPMENT',
        'production_authorized':False,'real_facility_data':False,
        'repository_implementation_evaluated':False,'independent_replication':False,
        'blocks':blocks,'tasks_per_block':8,
        'executions':len(records),'scores':{k:statistics.mean(v) for k,v in means.items()},
        'B6_minus_B5':statistics.mean(diff),'paired_block_bootstrap_95pct':bootstrap(diff),
        'unsafe_acceptance_counts':{k:sum(r['unsafe_acceptance'] for r in records if r['condition']==k) for k in LAYERS},
        'maximum_candidate_evaluations':max(r['candidate_evaluations'] for r in records),
        'source_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
        'not_scored':['verification completeness','unsupported claim rate','independent fidelity'],
        'limitations':['public synthetic development tasks','same author and implementations',
                      'no preregistered locked evaluation','no power justification','no real facility data',
                      'simplified symmetric routing and constant costs','no secure participant isolation']}
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    a=s.add_parser('adapter');a.add_argument('condition',choices=LAYERS)
    r=s.add_parser('run');r.add_argument('--output',type=Path,required=True);r.add_argument('--blocks',type=int,default=30)
    a=p.parse_args()
    if a.mode=='adapter':print(json.dumps(participant(json.load(sys.stdin),a.condition)))
    else:
        if not 2<=a.blocks<=100:p.error('blocks must be between 2 and 100')
        run(a.output,a.blocks)

if __name__=='__main__':main()
