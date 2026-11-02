"""Linux development runner. Resource limits are not a security sandbox."""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time

MAX_BYTES=65536

def limits(cpu,memory):
    os.setsid()
    resource.setrlimit(resource.RLIMIT_CPU,(math.ceil(cpu),math.ceil(cpu)+1))
    resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_BYTES,MAX_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def stop(pid):
    try:os.killpg(pid,signal.SIGKILL)
    except ProcessLookupError:pass

def run(command,payload,wall=60,cpu=30,memory=1024**3):
    if not command or wall<=0 or cpu<=0 or memory<32*1024**2:
        raise ValueError('invalid command or resource budget')
    started=time.monotonic();status='OK';usage=None;rc=None
    with tempfile.TemporaryDirectory(prefix='manufacturing-participant-') as work:
        root=Path(work)
        (root/'input.json').write_text(json.dumps(payload))
        with (root/'input.json').open('rb') as inp, (root/'stdout').open('w+b') as out, (root/'stderr').open('w+b') as err:
            p=subprocess.Popen(command,stdin=inp,stdout=out,stderr=err,cwd=work,
                env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONHASHSEED':'0'},
                close_fds=True,preexec_fn=lambda:limits(cpu,memory))
            while True:
                pid,waitstatus,usage=os.wait4(p.pid,os.WNOHANG)
                if pid:
                    rc=os.waitstatus_to_exitcode(waitstatus);p.returncode=rc;break
                if time.monotonic()-started>wall:
                    status='WALL_TIMEOUT';stop(p.pid)
                elif os.fstat(out.fileno()).st_size>=MAX_BYTES or os.fstat(err.fileno()).st_size>=MAX_BYTES:
                    status='OUTPUT_LIMIT';stop(p.pid)
                if status!='OK':
                    _,waitstatus,usage=os.wait4(p.pid,0)
                    rc=os.waitstatus_to_exitcode(waitstatus);p.returncode=rc;break
                time.sleep(.01)
            stop(p.pid)  # reap execution leader above; stop any same-session descendants
            out.seek(0);raw=out.read(MAX_BYTES+1)
            err.seek(0);stderr=err.read(MAX_BYTES).decode('utf-8','replace')
        elapsed=time.monotonic()-started
        if status=='OK' and rc!=0:status='PROCESS_FAILURE'
        if status=='OK' and (len(raw)>=MAX_BYTES or len(stderr.encode('utf-8'))>=MAX_BYTES):status='OUTPUT_LIMIT'
        submission=None
        if status=='OK':
            try:
                def unique(pairs):
                    result={}
                    for k,v in pairs:
                        if k in result:raise ValueError('duplicate JSON key')
                        result[k]=v
                    return result
                submission=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
                    parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
                if not isinstance(submission,dict):raise ValueError('object required')
            except (ValueError,UnicodeError,RecursionError):status='INVALID_OUTPUT'
        return {'status':status,'returncode':rc,'wall_seconds':elapsed,
                'cpu_seconds':usage.ru_utime+usage.ru_stime,
                'peak_rss_kib':usage.ru_maxrss,'stderr':stderr,
                'candidate_evaluations':'NOT_MEASURED','submission':submission}

