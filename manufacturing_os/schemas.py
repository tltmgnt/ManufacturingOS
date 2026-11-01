"""Export structural JSON Schemas and invoke authoritative runtime validation."""
from importlib.resources import files
import json
from pathlib import Path

from .calculations import Scenario
from .jsonio import loads,read_json
from .models import ManufacturingInput

CONTRACTS = {'input':'manufacturing-input.schema.json','scenario':'scenario.schema.json'}
VALIDATION_CONTRACTS = (*CONTRACTS,'study')


def get_schema(name: str) -> dict:
    if name not in CONTRACTS:
        raise ValueError('unknown contract name')
    return loads(files('manufacturing_os').joinpath('contracts',CONTRACTS[name]).read_bytes(),max_bytes=1024*1024)


def list_schemas() -> list[dict]:
    return [{'name':name,'title':get_schema(name)['title'],'schema_id':get_schema(name)['$id'],'contract_version':'1.0'}
            for name in sorted(CONTRACTS)]


def validate_contract(name: str,data: dict) -> dict:
    if name=='study':
        from .study import preflight_study
        return preflight_study(data)
    if name=='input':
        ManufacturingInput.from_dict(data)
    elif name=='scenario':
        Scenario.from_dict(data)
    else:
        raise ValueError('unknown contract name')
    return {'status':'VALID','contract':name,'contract_version':'1.0','validator':'AUTHORITATIVE_RUNTIME',
            'scope':'INPUT_CONTRACT_ONLY','production_authorized':False}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser=argparse.ArgumentParser(description='Export structural schemas or validate core input contracts without running a study')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('list')
    export=commands.add_parser('export')
    export.add_argument('name',choices=CONTRACTS)
    export.add_argument('--output',type=Path,help='Create a new JSON Schema file without overwriting')
    validate=commands.add_parser('validate')
    validate.add_argument('name',choices=VALIDATION_CONTRACTS)
    validate.add_argument('input',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='list':
            result=list_schemas()
        elif args.command=='export':
            result=get_schema(args.name)
        else:
            result=validate_contract(args.name,read_json(args.input))
        encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'
        if args.command=='export' and args.output:
            with args.output.open('x',encoding='utf-8') as file:
                file.write(encoded)
        else:
            print(encoded,end='')
    except (ValueError,TypeError,KeyError,OSError,OverflowError) as exc:
        print(f'Schema command error: {exc}',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
