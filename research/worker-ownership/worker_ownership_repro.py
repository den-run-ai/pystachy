#!/usr/bin/env python3
"""Deterministic reproductions for the blocked local process-worker extraction.

Run with the same Python used by the coordinator:
  python worker_ownership_repro.py /absolute/path/to/local-workers/tools

Both scenarios use ordinary in-group subprocess children. No worker daemonizes,
calls setsid, or changes its process group. Each independent coordinator is
launched in a private session, and this harness always kills that entire owned
group after collecting evidence. The cleanup race delays a real enumeration
result to force the otherwise timing-dependent fork-after-snapshot interleaving.

This file preserves the already-executed probes; it was not rerun after the
major-blocker stop. Observed outputs and source hashes are in the adjacent JSON.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


COMMON = r'''
import json, os, pathlib, signal, subprocess, sys, time
sys.path.insert(0, sys.argv[1]); import process_workers as workers
root=pathlib.Path(sys.argv[2])
child_source="import json,os,pathlib,sys,time; root=pathlib.Path(sys.argv[1]); (root/'child-ready').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp(),'started':time.monotonic()}));\nwhile not (root/'prove-alive').exists(): time.sleep(.001)\n(root/'child-proof').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp(),'after':time.monotonic()})); time.sleep(30)"
def wait_file(path):
    until=time.monotonic()+2
    while not path.exists() and time.monotonic()<until: time.sleep(.001)
    if not path.exists(): raise RuntimeError('probe handshake timed out: '+path.name)
'''

RESERVATION = COMMON + r'''
leader="import os,pathlib,subprocess,sys,time; root=pathlib.Path(sys.argv[2]); subprocess.Popen([sys.executable,'-c',sys.argv[1],str(root)]);\nwhile not (root/'child-ready').exists(): time.sleep(.001)\n"
next_job="import json,os,pathlib,sys,time; root=pathlib.Path(sys.argv[1]); started=time.monotonic(); (root/'prove-alive').touch();\nwhile not (root/'child-proof').exists(): time.sleep(.001)\nprint(json.dumps({'next_pid':os.getpid(),'next_pgid':os.getpgrp(),'started':started,'descendant':json.loads((root/'child-proof').read_text())}))"
commands=[workers.Job('leader',[sys.executable,'-c',leader,child_source,str(root)]),workers.Job('next',[sys.executable,'-c',next_job,str(root)])]
with workers.Commands() as scope:
    results=list(scope.run(commands,dict(os.environ),timeout=2,jobs=1))
print(json.dumps({'coordinator_pid':os.getpid(),'coordinator_pgid':os.getpgrp(),'complete':all(r['exit_code']==0 for r in results),'peak_cpu':scope.peak_reserved['cpu'],'leader_finished':results[0]['finished_monotonic_s'],'next_admitted':results[1]['started_monotonic_s'],'proof':json.loads(results[1]['stdout'])}))
'''

ESCALATION_RACE = COMMON + r'''
leader="import os,pathlib,signal,subprocess,sys,time; root=pathlib.Path(sys.argv[2]); signal.signal(signal.SIGTERM,signal.SIG_IGN); (root/'leader-ready').write_text(str(os.getpid()));\nwhile not (root/'trigger-fork').exists(): time.sleep(.001)\nsubprocess.Popen([sys.executable,'-c',sys.argv[1],str(root)]); time.sleep(30)"
scope=workers.Commands(cleanup_grace=.25); original=workers.group_members; calls=0; last_snapshot=[]
def delayed_enumeration():
    global calls,last_snapshot
    snapshot=original()
    if any(state['cancelled'] for state in scope.running.values()):
        calls+=1
        if calls==2:
            last_snapshot=snapshot
            (root/'trigger-fork').touch(); wait_file(root/'child-ready'); time.sleep(.3)
    return snapshot
workers.group_members=delayed_enumeration
try:
    with scope:
        list(scope.run([workers.Job('leader',[sys.executable,'-c',leader,child_source,str(root)])],dict(os.environ),timeout=.1,jobs=1))
except TimeoutError: pass
ended=time.monotonic(); (root/'prove-alive').touch(); wait_file(root/'child-proof')
print(json.dumps({'coordinator_pid':os.getpid(),'coordinator_pgid':os.getpgrp(),'last_snapshot':last_snapshot,'leader_pid':int((root/'leader-ready').read_text()),'child_started':json.loads((root/'child-ready').read_text()),'scope_exit':ended,'proof_after_scope_exit':json.loads((root/'child-proof').read_text()),'cleanup_enumerations':calls,'direct_results':len(scope.results)}))
'''


def main():
    if len(sys.argv) != 2 or not (Path(sys.argv[1]) / "process_workers.py").is_file():
        raise SystemExit("usage: worker_ownership_repro.py /absolute/path/to/tools")
    tools = str(Path(sys.argv[1]).resolve())
    for name, script in (("reservation", RESERVATION), ("escalation_race", ESCALATION_RACE)):
        with tempfile.TemporaryDirectory(prefix="pystachy-worker-audit-") as temporary:
            process = subprocess.Popen(
                [sys.executable, "-c", script, tools, temporary],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
            )
            try:
                output, error = process.communicate(timeout=8)
                print(name, "exit", process.returncode, "result", output.strip(), "stderr", error.strip()[:1000])
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


if __name__ == "__main__":
    main()
