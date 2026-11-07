"""Local validation orchestration; delegates comparisons to maintained repository tools."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time

ROOT = Path('/workspace/scratch/5798eb31a437/field-errors')
BASE = Path('/workspace/scratch/5798eb31a437/compiler-work')
OUT = Path('/workspace/scratch/5798eb31a437/baseline-evidence/field-errors-validation')
LLVM = Path('/workspace/scratch/e98dc1e3e6cd/toolchains/ubuntu-18.1.3-1ubuntu1-amd64/bin')
os.sched_setaffinity(0, {0, 1, 2, 3})
env = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_') and k not in ('PYTHONHOME', 'PYTHONPATH')}
env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_LLVM=str(LLVM), PYSTACHY_JOBS='2', PYSTACHY_BUILD_JOBS='1',
           PYSTACHY_IRCHECK='1', PYSTACHY_CACHE=str(OUT / 'cache'), PYTHONHASHSEED='0')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

report = dict(complete=False, candidate_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              baseline=str(BASE), candidate=str(ROOT), baseline_binary_sha256=sha(BASE/'pystachy'),
              candidate_binary_sha256=sha(ROOT/'pystachy'), affinity=sorted(os.sched_getaffinity(0)), commands=[],
              input_assumption='Compiler implementations remain distinct; full corpus explicitly shares baseline home after all lib/runtime input bytes were verified equal.')

def save():
    (OUT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')

def run(label, command, overrides=None, allowed=(0,), timeout=1200):
    settings=dict(env)
    if overrides:
        settings.update(overrides)
    log=OUT/(label+'.log')
    row=dict(label=label,command=[str(x) for x in command], environment={k:v for k,v in settings.items() if k.startswith('PYSTACHY_')},
             load_before=os.getloadavg())
    report['commands'].append(row)
    save()
    print('starting '+label,flush=True)
    started=time.monotonic()
    child=None
    try:
        with log.open('wb') as stream:
            child=subprocess.Popen(row['command'],cwd=ROOT,env=settings,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            row['returncode']=child.wait(timeout=timeout)
    except BaseException:
        if child is not None:
            try:
                os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=2)
        raise
    finally:
        row.update(wall_s=time.monotonic()-started,log_sha256=sha(log),load_after=os.getloadavg())
        save()
    if row['returncode'] not in allowed:
        raise RuntimeError(label+' failed: '+log.read_text(errors='replace')[-5000:])
    print('finished '+label+' ('+str(row['returncode'])+')',flush=True)
    return row

try:
    witness='tests/programs/apps/example_linediff.py'
    module_path=subprocess.check_output(['sh','tests/prepare_path.sh',witness,str(OUT)],cwd=ROOT,text=True).strip()
    for label, compiler, home in [('path-base',BASE/'pystachy',BASE),('path-head-own',ROOT/'pystachy',ROOT),('path-head-shared',ROOT/'pystachy',BASE)]:
        run(label,[compiler,'ir',witness,'-o',OUT/(label+'.ll')],{'PYSTACHY_HOME':str(home),'PYSTACHY_PATH':module_path})
    old=(OUT/'path-base.ll').read_bytes()
    own=(OUT/'path-head-own.ll').read_bytes()
    shared=(OUT/'path-head-shared.ll').read_bytes()
    if old == own or old != shared:
        raise RuntimeError('focused home-path witness did not isolate the path difference')
    (OUT/'path-only.diff').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),own.decode().splitlines(True),fromfile='baseline-home',tofile='candidate-home')))
    report['path_witness']={'case':witness,'module_path':module_path,'independent_home_differs':True,'shared_home_identical':True,'baseline_sha256':sha(OUT/'path-base.ll'),'own_home_sha256':sha(OUT/'path-head-own.ll'),'shared_home_sha256':sha(OUT/'path-head-shared.ll')}
    save()
    run('full-corpus',['sh','build/irsame_capture.sh',BASE/'pystachy',ROOT/'pystachy'],{'PYSTACHY_HOME':str(BASE)},allowed=(0,1))
    capture=Path((ROOT/'build/field-corpus-directory.txt').read_text().strip())
    cases=(capture/'cases.txt').read_text().splitlines()
    changes=[]
    for i, case in enumerate(cases,1):
        directory=capture/str(i)
        result=(directory/'report').read_text()
        if not result:
            continue
        if not result.startswith('  IR ') or any(marker in result for marker in ('\n  exit status','\n  messages:','IR written by only one compiler','no result')):
            raise RuntimeError('unexpected diagnostic/status/output change in '+case+': '+result)
        a,b=directory/'old.ll',directory/'new.ll'
        text=b.read_text()
        if not any(line.startswith('@pys.field.names =') for line in text.splitlines()):
            raise RuntimeError('IR changed without a field-name table in '+case)
        changes.append({'case':case,'directory':str(directory),'old_sha256':sha(a),'new_sha256':sha(b),
                        'old_bytes':a.stat().st_size,'new_bytes':b.stat().st_size})
        (directory/'full.diff').write_text(''.join(difflib.unified_diff(a.read_text().splitlines(True),text.splitlines(True),fromfile=case+':baseline',tofile=case+':candidate')))
        run('verify-changed-'+str(i),[LLVM/'llvm-as',b,'-o',os.devnull])
    report['corpus']={'cases':len(cases),'exact_comparisons':len(cases)-len(changes),'intentional_ir_differences':changes,
                      'exact_diagnostics_status':len(cases),'capture_directory':str(capture),
                      'comparison_patch_sha256':sha(ROOT/'build/irsame_capture.patch')}
    save()
    focused=(ROOT/'build/field-error-cases.txt').read_text().splitlines()
    affected=[r['case'] for r in changes if r['case'].startswith('tests/programs/')]
    programs=sorted(set(focused+affected))
    report['native_cases']=programs
    report['program_gc_cases']=focused
    run('native',['sh','tests/run.sh','./pystachy','jit aot',*programs])
    run('program-gc',['sh','tests/run.sh','./pystachy','jit aot',*focused],{'PYSTACHY_GC_STRESS_PROGRAM':'1'})
    dry=OUT/'dry_field_error.py'
    dry.write_text('''class Base:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7
class Child(Base):
    pass

def read(obj: Base) -> int:
    value = None
    print(value)
    value = obj.value
    return value
print(read(Child(True)))
''')
    report['compiler_gc']=[]
    for label, source in [('fixture',ROOT/'tests/programs/classes/inheritance_field_errors.py'),('dry',dry)]:
        for mode in ('normal','stress'):
            output=OUT/(label+'-'+mode+'.ll')
            run('compiler-'+label+'-'+mode,[ROOT/'pystachy','ir',source,'-o',output],{'PYSTACHY_GC_STRESS':'1' if mode=='stress' else ''})
        normal,stress=OUT/(label+'-normal.ll'),OUT/(label+'-stress.ll')
        if normal.read_bytes()!=stress.read_bytes():
            raise RuntimeError('compiler allocation stress changed IR for '+label)
        run('verify-'+label,[LLVM/'llvm-as',normal,'-o',os.devnull])
        report['compiler_gc'].append({'case':str(source),'identical_ir':True,'sha256':sha(normal)})
    shared_inputs=json.loads((OUT/'shared-inputs.json').read_text())
    previous=shared_inputs['before']
    after={name:{p:sha(root/p) for p in previous[name]} for name,root in [('baseline',BASE),('candidate',ROOT)]}
    shared_inputs.update(after=after,unchanged=after==previous,identical_after=after['baseline']==after['candidate'])
    (OUT/'shared-inputs.json').write_text(json.dumps(shared_inputs,indent=2,sort_keys=True)+'\n')
    if not shared_inputs['unchanged'] or not shared_inputs['identical_after']:
        raise RuntimeError('library/runtime inputs changed during the corpus validation')
    if sha(BASE/'pystachy')!=report['baseline_binary_sha256'] or sha(ROOT/'pystachy')!=report['candidate_binary_sha256']:
        raise RuntimeError('compiler executable changed during validation')
    shutil.copyfile(ROOT/'build/irsame_capture.patch',OUT/'irsame-capture.patch')
    report['complete']=True
except BaseException as error:
    report['error']=repr(error)
    raise
finally:
    save()
    print(json.dumps({k:report.get(k) for k in ('complete','error')},sort_keys=True),flush=True)
