"""Build-independent wheel smoke check in a clean venv outside the checkout.

Usage: python tests/smoke_installed.py dist/manufacturingos-0.1.0-py3-none-any.whl
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    wheel=Path(sys.argv[1]).resolve()
    with zipfile.ZipFile(wheel) as archive:
        paths=archive.namelist()
        assert not any(path.startswith(('tests/','runs/','examples/')) for path in paths)
        assert 'manufacturing_os/cli.py' in paths
        assert 'manufacturing_os/contracts/manufacturing-input.schema.json' in paths
        assert 'manufacturing_os/contracts/scenario.schema.json' in paths
        metadata=archive.read(next(path for path in paths if path.endswith('.dist-info/METADATA'))).decode()
        assert '\nRequires-Dist:' not in metadata, 'unexpected runtime dependencies'
    with tempfile.TemporaryDirectory() as directory:
        working=Path(directory)
        environment=working/'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        bindir=environment/('Scripts' if os.name=='nt' else 'bin')
        python=bindir/('python.exe' if os.name=='nt' else 'python')
        executable=bindir/('manufacturing-os.exe' if os.name=='nt' else 'manufacturing-os')
        env=dict(os.environ)
        env.pop('PYTHONPATH',None)
        def run(command):
            result=subprocess.run(list(map(str,command)),cwd=working,env=env,capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError(f"Command failed ({result.returncode}): {command}\n{result.stdout}\n{result.stderr}")
            return result.stdout
        run([python,'-m','pip','install','--no-index','--no-deps',wheel])
        version=run([executable,'--version']).strip()
        location=run([python,'-c','import manufacturing_os; print(manufacturing_os.__file__)']).strip()
        assert Path(location).resolve().is_relative_to(environment.resolve()), location
        for command in ['plan','estimate','experiment','simulate','study','review','compare','bundle','evidence','sources','capture','notes','replicate','observations','campaign','campaign-bundle','schema']:
            run([executable,command,'--help'])
        evidence=json.loads(run([executable,'evidence',ROOT/'examples/evidence-input.json',ROOT/'examples/evidence-policy.json']))
        assert evidence['status']=='METADATA_CHECKS_PASSED'
        sources=json.loads(run([executable,'sources',ROOT/'examples/source-input.json',ROOT/'examples/source-snapshot.json']))
        assert sources['status']=='CAPTURED_CONTENT_COVERED'
        if os.name=='posix':
            captured=working/'captured.json'
            run([executable,'capture',ROOT/'examples/source-input.json',ROOT/'examples/capture-manifest.json','--root',ROOT/'examples/source-files','--output',captured])
            assert json.loads(captured.read_text())==json.loads((ROOT/'examples/source-snapshot.json').read_text())
        downtime=json.loads(run([executable,'simulate',ROOT/'examples/finite-batch-downtime.json']))
        assert len(downtime['normalized_downtime'])==1
        assert downtime['target_met'] is False
        batch_costs=json.loads(run([executable,'simulate',ROOT/'examples/finite-batch-costs.json']))['cost_report']
        assert batch_costs['scope']=='FULL_SIMULATED_BATCH'
        assert batch_costs['unit_cost'] is not None
        replicated=json.loads(run([executable,'replicate',ROOT/'examples/replication-experiment.json']))
        assert replicated['run_count']==20
        replay=json.loads(run([executable,'replicate',ROOT/'examples/replication-experiment.json','--replay','0']))
        assert replay['input']['seed']==replicated['outcomes'][0]['seed']
        observation_study=working/'observation-study.json'
        run([executable,'study',ROOT/'examples/observation-study.json','--output',observation_study])
        checked=json.loads(run([executable,'observations',observation_study]))
        assert checked['status']=='PASS' and len(checked['checks'])==6
        campaign=json.loads(run([executable,'campaign',ROOT/'examples/scenario-campaign.json']))
        assert campaign['status']=='PASS' and campaign['revision_required_studies']==3
        campaign_bundle=working/'campaign.zip'
        run([executable,'campaign-bundle','create',ROOT/'examples/scenario-campaign.json','--output',campaign_bundle])
        checked_campaign=json.loads(run([executable,'campaign-bundle','verify',campaign_bundle]))
        assert checked_campaign['campaign_status']=='PASS' and checked_campaign['revision_required_studies']==3
        ambiguous=working/'ambiguous.json'
        valid_spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        ambiguous.write_text('{"schema_version":"1.0",'+json.dumps(valid_spec)[1:])
        rejected=subprocess.run([str(executable),'study',str(ambiguous)],cwd=working,env=env,capture_output=True,text=True)
        assert rejected.returncode==2 and 'duplicate JSON key' in rejected.stderr
        schema_file=working/'scenario.schema.json'
        run([executable,'schema','export','scenario','--output',schema_file])
        assert json.loads(schema_file.read_text())['title']=='Serial-route Scenario v1.0'
        validated=json.loads(run([executable,'schema','validate','scenario',ROOT/'examples/serial-route.json']))
        assert validated['status']=='VALID' and validated['production_authorized'] is False
        preflight=json.loads(run([executable,'schema','validate','study',ROOT/'examples/observation-study.json']))
        assert preflight['analysis_executed'] is False and preflight['scope']=='STUDY_INPUT_PREFLIGHT'
        before=working/'before.json'
        after=working/'after.json'
        review=working/'review.html'
        comparison=working/'comparison.json'
        bundle=working/'bundle.zip'
        run([executable,'study',ROOT/'examples/integrated-study.json','--output',before])
        run([executable,'study',ROOT/'examples/integrated-study-revised.json','--output',after])
        notes=working/'notes.json'
        run([executable,'notes','add',after,'--note-id','smoke-note','--reviewer','Synthetic reviewer','--role','quality','--timestamp','2026-11-01T00:00:00Z','--comment','Synthetic smoke annotation','--disposition','COMMENT','--output',notes])
        run([executable,'notes','check',after,notes])
        run([executable,'review',after,'--notes',notes,'--output',review])
        run([executable,'compare',before,after,'--output',comparison])
        run([executable,'bundle','create',ROOT/'examples/integrated-study-revised.json','--before',before,'--notes',notes,'--output',bundle])
        verified=json.loads(run([executable,'bundle','verify',bundle]))
        assert verified['status']=='VERIFIED_CONTENT'
        assert verified['production_authorized'] is False
        print(json.dumps({'version':version,'isolated_install':'PASS','workflow':'PASS','bundle':verified['status']}))


if __name__=='__main__':
    main()
