from pathlib import Path
import os, subprocess, json, time, hashlib
root=Path('/workspace/scratch/0bc6e8bc1edf')
repo=root/'match-main'
py=str(root/'dev-venv/bin/python')
env={k:v for k,v in os.environ.items() if not k.startswith('PYSTACHY_')}
env.update(PYSTACHY_LLVM=str(root/'llvm18/usr/lib/llvm-18/bin'),PYSTACHY_HOME=str(repo),PYSTACHY_CACHE=str(root/'audit-native-cache'),PYSTACHY_PROGRAM_CACHE='0')
(root/'audit_promoting_scalar.py').write_text('''# pystachy: python-int
def f(x:int)->str:
    match x:
        case (a,b): return 'tuple'
        case _: return 'scalar'
print(f(1),f(1 << 100),f(-(1 << 100)))
''')
cases=['module_binding','global_binding','empty_class_none','nested_dc','guard_exception_capture','pattern_exception_capture','value_enum','empty_sequence','huge_hex','huge_hex_no_e','promoting_scalar']
report={'started':time.time(),'source_hash':hashlib.sha256((repo/'src/pystachy_compiler/patterns.py').read_bytes()).hexdigest(),'cases':[]}
for name in cases:
    p=root/('audit_'+name+'.py'); exe=root/('audit_'+name+'.exe')
    expected=subprocess.run([py,str(p)],capture_output=True,text=True,env=env,cwd=repo,timeout=30)
    row={'name':name,'expected_rc':expected.returncode,'expected_stdout':expected.stdout,'expected_stderr':expected.stderr,'checks':[]}
    print('CASE',name,'expected',repr(expected.stdout),flush=True)
    for stress in [False,True]:
        runenv=env.copy()
        if stress: runenv['PYSTACHY_GC_STRESS_PROGRAM']='1'
        start=time.monotonic()
        r=subprocess.run([py,'-m','pystachy','run',str(p)],capture_output=True,text=True,env=runenv,cwd=repo,timeout=240)
        ok=(r.returncode,r.stdout,r.stderr)==(expected.returncode,expected.stdout,expected.stderr)
        row['checks'].append({'mode':'jit','gc_stress':stress,'ok':ok,'seconds':time.monotonic()-start,'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        print(' JIT',stress,'PASS' if ok else 'FAIL',r.returncode,r.stderr[:500],flush=True)
    start=time.monotonic()
    build=subprocess.run([py,'-m','pystachy','build',str(p),'-o',str(exe)],capture_output=True,text=True,env=env,cwd=repo,timeout=240)
    row['build']={'rc':build.returncode,'stderr':build.stderr,'seconds':time.monotonic()-start}
    print(' BUILD',build.returncode,build.stderr[:500],flush=True)
    if build.returncode==0:
        for stress in [False,True]:
            runenv=env.copy()
            if stress:
                runenv['PYSTACHY_GC_STRESS_PROGRAM']='1'
                runenv['PYSTACHY_GC_STRESS']='1'
            start=time.monotonic()
            r=subprocess.run([str(exe)],capture_output=True,text=True,env=runenv,cwd=repo,timeout=30)
            ok=(r.returncode,r.stdout,r.stderr)==(expected.returncode,expected.stdout,expected.stderr)
            row['checks'].append({'mode':'aot','gc_stress':stress,'ok':ok,'seconds':time.monotonic()-start,'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
            print(' AOT',stress,'PASS' if ok else 'FAIL',r.returncode,r.stderr[:500],flush=True)
    report['cases'].append(row)
    (root/'match_audit_native_results.json').write_text(json.dumps(report,indent=2))
report['finished']=time.time()
report['passed']=sum(check['ok'] for row in report['cases'] for check in row['checks'])
report['comparisons']=sum(len(row['checks']) for row in report['cases'])
(root/'match_audit_native_results.json').write_text(json.dumps(report,indent=2))
print('RESULT',report['passed'],report['comparisons'],flush=True)
