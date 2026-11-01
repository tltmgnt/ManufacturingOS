"""Independent standards check. Dev tool: pip install 'jsonschema>=4.18,<5'."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from jsonschema import Draft202012Validator
from manufacturing_os.schemas import get_schema,validate_contract


def main():
    packages=[json.loads((ROOT/'examples'/name).read_text()) for name in ['synthetic-cnc.json','evidence-input.json','source-input.json']]
    scenario=json.loads((ROOT/'examples/serial-route.json').read_text())
    validators={name:Draft202012Validator(get_schema(name)) for name in ['input','scenario']}
    for validator in validators.values():
        Draft202012Validator.check_schema(validator.schema)
    positive=negative=gaps=0
    for data in packages:
        validators['input'].validate(data)
        positive+=1
    validators['scenario'].validate(scenario)
    positive+=1
    for name,data in [('input',packages[0]),('scenario',scenario)]:
        for key in data:
            bad=deepcopy(data)
            del bad[key]
            assert list(validators[name].iter_errors(bad)),(name,key)
            negative+=1
        bad={**deepcopy(data),'unexpected':True}
        assert list(validators[name].iter_errors(bad))
        negative+=1
    bad=deepcopy(scenario)
    bad['operations'][0]['cycle_time']['value']=0
    assert list(validators['scenario'].iter_errors(bad))
    negative+=1
    bad=deepcopy(packages[0])
    bad['constraints'][0]['satisfied']=True
    assert list(validators['input'].iter_errors(bad))
    negative+=1
    # Explicitly demonstrate documented structural/semantic boundaries.
    gap_cases=[]
    duplicate=deepcopy(packages[0]); duplicate['bom']*=2
    gap_cases.append(('input',duplicate))
    currency=deepcopy(scenario); currency['operations'][0]['machine_rate']['unit']='EUR/h'
    gap_cases.append(('scenario',currency))
    integer=deepcopy(scenario); integer['target_good_units']=1.0
    gap_cases.append(('scenario',integer))
    for name,data in gap_cases:
        validators[name].validate(data)
        try:
            validate_contract(name,data)
        except (ValueError,TypeError):
            gaps+=1
        else:
            raise AssertionError('runtime must reject documented semantic gap')
    print(json.dumps({'schema_documents':2,'positive_fixtures':positive,'invalid_fixtures_rejected':negative,'documented_semantic_boundaries':gaps,'status':'PASS'}))


if __name__=='__main__':
    main()
