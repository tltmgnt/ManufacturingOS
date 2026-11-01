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
        for command in ['plan','estimate','experiment','simulate','study','review','compare','bundle','evidence','sources','capture']:
            run([executable,command,'--help'])
        evidence=json.loads(run([executable,'evidence',ROOT/'examples/evidence-input.json',ROOT/'examples/evidence-policy.json']))
        assert evidence['status']=='METADATA_CHECKS_PASSED'
        sources=json.loads(run([executable,'sources',ROOT/'examples/source-input.json',ROOT/'examples/source-snapshot.json']))
        assert sources['status']=='CAPTURED_CONTENT_COVERED'
        if os.name=='posix':
            captured=working/'captured.json'
            run([executable,'capture',ROOT/'examples/source-input.json',ROOT/'examples/capture-manifest.json','--root',ROOT/'examples/source-files','--output',captured])
            assert json.loads(captured.read_text())==json.loads((ROOT/'examples/source-snapshot.json').read_text())
        before=working/'before.json'
        after=working/'after.json'
        review=working/'review.html'
        comparison=working/'comparison.json'
        bundle=working/'bundle.zip'
        run([executable,'study',ROOT/'examples/integrated-study.json','--output',before])
        run([executable,'study',ROOT/'examples/integrated-study-revised.json','--output',after])
        run([executable,'review',after,'--output',review])
        run([executable,'compare',before,after,'--output',comparison])
        run([executable,'bundle','create',ROOT/'examples/integrated-study-revised.json','--before',before,'--output',bundle])
        verified=json.loads(run([executable,'bundle','verify',bundle]))
        assert verified['status']=='VERIFIED_CONTENT'
        assert verified['production_authorized'] is False
        print(json.dumps({'version':version,'isolated_install':'PASS','workflow':'PASS','bundle':verified['status']}))


if __name__=='__main__':
    main()
