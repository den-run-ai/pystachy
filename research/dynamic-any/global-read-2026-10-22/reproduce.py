import fcntl, hashlib, json, os, pathlib, re, statistics, subprocess, sys, time
W=pathlib.Path(os.environ['MEASURE_OUTPUT']).resolve(); W.mkdir(parents=True,exist_ok=True)
R=pathlib.Path(os.environ['CANDIDATE_ROOT']).resolve()
lock=open(W/'measurement.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sys.path.insert(0,str(R/'tools'))
import perf_smoke
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
env={k:v for k,v in os.environ.items() if not k.startswith('PYSTACHY_') and k not in ['PYTHONPATH','PYTHONHOME']}
env.update(PYSTACHY_HOME=str(R),PYSTACHY_LLVM=os.environ['PYSTACHY_LLVM'],PYTHONHASHSEED='0')
compilers={'main':os.environ['MAIN_COMPILER'],'parent':os.environ['PARENT_COMPILER'],'candidate':str(R/'pystachy')}
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
report={'sources':{'main':'7514bef719ca8cfe5ad816060574c54f25fd5e2d','parent':'db4b8517b730eb0c365995e315520434dde8a5cc','candidate':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()},'python':sys.version,'affinity':list(os.sched_getaffinity(0)),'load':os.getloadavg(),'compiler_binaries':{k:{'path':v,'sha256':sha(v)} for k,v in compilers.items()},'runtime_note':'All compiler variants use the identical candidate runtime/library inputs. No runtime or library files differ across these three source trees. Parent binary built from 7903da7a whose tree equals db4b8517. Main binary from ref/commit 7514bef7. Candidate full bootstrap log retained.','results':{},'paired':{}}
(W/'measurements').mkdir(exist_ok=True)
source=pathlib.Path(__file__).with_name('numeric_global4.py')
report['source_sha256']=sha(source)
meter=os.environ['RSS_METER']
for label,compiler in compilers.items():
    e=dict(env,PYSTACHY_CACHE=str(W/'measurements'/('cache-'+label)))
    subprocess.run([compiler,'build',str(source),'-o',str(W/'measurements'/label)],env=e,cwd=R,check=True,capture_output=True,timeout=180)
for mode,n in [('int',2000000),('float',1000000),('int',6000000),('float',6000000)]:
    args=[mode,str(n),'123']
    expected=int(subprocess.check_output([sys.executable,str(source),*args],text=True).split()[0])
    def sample(label,gc=False):
        e=dict(env)
        if gc:e['PYSTACHY_GC']='stats'
        r=subprocess.run([meter,str(W/'measurements'/label),*args],env=e,capture_output=True,text=True,check=True,timeout=30)
        values=list(map(int,r.stdout.split()));assert values[0]==expected
        m=re.search(r'WATCH_RSS_KIB (\d+) CPU_S ([\d.]+)',r.stderr);assert m
        return dict(loop_s=values[1]/1e9,loop_cpu_s=values[2]/1e9,rss_kib=int(m[1]),process_cpu_s=float(m[2]),stderr=r.stderr)
    for label in compilers:sample(label)
    rows=[]
    for i in range(10):
        order=list(compilers) if i%2==0 else list(reversed(compilers))
        rows.append({label:sample(label) for label in order})
    medians={label:{metric:statistics.median(row[label][metric] for row in rows) for metric in ['loop_s','loop_cpu_s','rss_kib','process_cpu_s']} for label in compilers}
    report['results'][f'{mode}-{n}']={'checksum':expected,'samples':rows,'medians':medians,'gc':{label:sample(label,True) for label in compilers}}
    print(mode,n,json.dumps(medians),flush=True)
    (W/'measurement.json').write_text(json.dumps(report,indent=2)+'\n')
for baseline in ['main','parent']:
    directory=W/'measurements'/('paired-'+baseline)
    directory.mkdir(exist_ok=True)
    comps={'base':compilers[baseline],'head':compilers['candidate']}
    envs={side:dict(env,PYSTACHY_CACHE=str(directory/side/'cache')) for side in comps}
    for side in comps:(directory/side).mkdir(exist_ok=True)
    results=[];built=set()
    # Keep maintained cases, thresholds and confirmation batches unchanged.
    for name in perf_smoke.CASES:
        print('paired',baseline,name,flush=True)
        results.append(perf_smoke.measure(name,comps,envs,directory,built))
        report['paired'][baseline]=results
        (W/'measurement.json').write_text(json.dumps(report,indent=2)+'\n')
    for result in results:
        for metric,c in result['comparison'].items():
            print(baseline,result['name'],metric,round((c['ratio']-1)*100,1),c['status'],flush=True)
