#!/usr/bin/env python3
"""Current-main versus integrated-candidate normal-driver comparison for PR996.

Current main and candidate require fresh, complete bootstrap records. The da84
role is an explicitly historical source reference with its archived build and
strictly revalidated LLVM instruction profiles. Elapsed observations are all new.
"""
from pathlib import Path
import argparse,datetime,difflib,hashlib,itertools,json,math,os,platform,re,resource,shutil,signal,statistics,subprocess,sys,time
ROOT=Path(__file__).resolve().parent
OLD=Path('/workspace/scratch/e858f72517b9')
SOURCE=OLD/'baselines/old-eca/bench/smoke/text.py'
HOMES={'main':ROOT.parent/'main1000','da84':OLD/'pystachy','final':ROOT.parent/'pystachy'}
COMMITS={'da84':'da84d382ff83f09e46d4ef104e62e6f64e9c37c1'}
ROLE_SCOPES={'main':'current main: primary acceptance baseline; fresh bootstrap and new tool profiles',
 'da84':'historical source/build reference: pre-follow-up PR996 head on main06e3; not current main; elapsed samples are new, instruction profiles are validated archive reuse',
 'final':'integrated candidate containing current main: fresh bootstrap and new tool profiles'}
CASES={'fnmatch':['fnmatch','1000'],'json':['json','6000'],'repair_scan':['repair_scan','400']}
ORDERS=list(itertools.permutations(HOMES))
ARCHIVE=OLD/'perf-work/backend-attribution-da84'
BOOTSTRAP_EXCLUSIONS={'Makefile','VERSION','.python-version'}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def git(home,*args):return subprocess.check_output(['git',*args],cwd=home,text=True).strip()
def identity(home):
 paths=[home/name for name in ['pystachy.py','runtime.c','runtime.py','pyext.c','pyembed.c','Makefile','VERSION','.python-version']]
 for folder in ['src','lib','mpz','ryu']:
  paths += [p for p in (home/folder).rglob('*') if p.is_file() and p.suffix in ['.py','.c','.h']]
 return {'directory':str(home),'commit':git(home,'rev-parse','HEAD'),'tree':git(home,'rev-parse','HEAD^{tree}'),'git_status':git(home,'status','--porcelain=v1'),'inputs':{str(p.relative_to(home)):digest(p) for p in sorted(set(paths)) if p.exists()},'native_sha256':digest(home/'pystachy')}
def execute(cmd,env,cwd,timeout=90,expected=None,kernel=False):
 cmd=[str(x) for x in cmd];before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
 with subprocess.Popen(cmd,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True) as p:
  try:stdout,stderr=p.communicate(timeout=timeout)
  except BaseException as error:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   stdout,stderr=p.communicate()
   if isinstance(error,subprocess.TimeoutExpired):raise RuntimeError({'timeout':timeout,'command':cmd,'stdout':stdout,'stderr':stderr}) from error
   raise
 elapsed=time.perf_counter()-start;after=resource.getrusage(resource.RUSAGE_CHILDREN)
 row={'command':cmd,'cwd':str(cwd),'returncode':p.returncode,'wall_s':elapsed,'cpu_s':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'stdout':stdout,'stderr':stderr}
 if p.returncode or expected is not None and stdout!=expected:raise RuntimeError(row)
 if kernel:
  times=re.findall(r'^seconds ([0-9.eE+-]+)$',stderr,re.M);assert len(times)==1,row
  row['loop_s']=float(times[0]);assert math.isfinite(row['loop_s']) and row['loop_s']>0,row
  row['outside_loop_s']=elapsed-row['loop_s'];assert row['outside_loop_s']>=0,row
 return row

def main():
 def interrupted(signum,frame):raise InterruptedError('received signal '+str(signum))
 for sig in [signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,interrupted)
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['prepare','timings','profile']);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--expected-final-commit',required=True);parser.add_argument('--bootstrap',type=Path,required=True)
 parser.add_argument('--main-home',type=Path,required=True);parser.add_argument('--main-bootstrap',type=Path,required=True);parser.add_argument('--expected-main-commit',required=True);parser.add_argument('--final-home',type=Path,default=HOMES['final']);args=parser.parse_args()
 out=args.output.resolve();args.bootstrap=args.bootstrap.resolve();args.main_bootstrap=args.main_bootstrap.resolve();path=out/'report.json';real=Path(os.environ['PYSTACHY_LLVM']).resolve()
 HOMES['main']=args.main_home.resolve();HOMES['final']=args.final_home.resolve();COMMITS['main']=args.expected_main_commit
 clean={k:v for k,v in os.environ.items() if not k.startswith(('PYSTACHY_','ATTR_')) and k not in ['PYTHONPATH','PYTHONHOME']}
 clean.update(PYSTACHY_LLVM=str(real),PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1')
 os.sched_setaffinity(0,{0});COMMITS['final']=args.expected_final_commit
 if args.phase=='prepare':
  out.mkdir(exist_ok=False)
  ids={k:identity(v) for k,v in HOMES.items()}
  for k,v in ids.items():assert v['commit']==COMMITS[k] and v['git_status']=='',(k,v['commit'],v['git_status'])
  # Explicit bootstrap record accompanies the final binaries; caller supplied
  # expected commit plus unchanged source/native hashes bind every later phase.
  assert subprocess.run(['git','merge-base','--is-ancestor',COMMITS['main'],COMMITS['final']],cwd=HOMES['final'],check=False).returncode==0,'candidate must contain current main'
  bootstrap_paths={'main':args.main_bootstrap,'da84':OLD/'recovery-validation/final-da84/bootstrap.json','final':args.bootstrap}
  bootstraps={role:json.loads(p.read_text()) for role,p in bootstrap_paths.items()};fixed={};excluded={};bootstrap_inputs={};bootstrap_logs={}
  for role,home in HOMES.items():
   bootstrap=bootstraps[role];ident=ids[role]
   if role in ['main','final']:
    assert bootstrap.get('fresh_local_build') is True and bootstrap.get('record_kind')!='equivalent_build_binding',(role,'fresh full bootstrap required')
    assert Path(bootstrap['source']).resolve()==home,(role,'bootstrap source directory')
    assert bootstrap['llvm']==str(real) and bootstrap['python']==sys.version,(role,'bootstrap toolchain')
    log=bootstrap_paths[role].parent/'bootstrap.log';assert digest(log)==bootstrap['log_sha256'],(role,'bootstrap log')
    bootstrap_logs[role]={'path':str(log),'sha256':digest(log)}
   assert bootstrap.get('status') in ['passed','complete'],(role,bootstrap.get('status'))
   assert bootstrap['commit']==COMMITS[role] and bootstrap['tree']==ident['tree']
   assert bootstrap['artifacts']['pystachy']['sha256']==ident['native_sha256']
   assert bootstrap['exit_code']==0 and bootstrap['source_identity_stable'] and bootstrap['before']==bootstrap['after']
   assert set(bootstrap['artifacts'])=={'pystachy','build/pystachy1','build/pystachy2',*[f'build/stage{n}.ll' for n in [1,2,3]],*[f'build/rt{n}.ll' for n in [1,2,3]]},(role,'all nine build artifacts required')
   for name,value in bootstrap['before'].items():
    source=home/name;assert digest(source)==value,(role,name,'bootstrap consumed input')
    bootstrap_inputs[str(source)]=value
   missing=set(ident['inputs'])-set(bootstrap['before']);assert missing<=BOOTSTRAP_EXCLUSIONS,(role,missing)
   excluded[role]={name:ident['inputs'][name] for name in sorted(missing)}
   for name,value in ident['inputs'].items():
    if name in missing:
     assert hashlib.sha256(subprocess.check_output(['git','show',COMMITS[role]+':'+name],cwd=home)).hexdigest()==value,(role,name)
    else:assert bootstrap['before'][name]==value,(role,name)
   for name,value in bootstrap['artifacts'].items():assert digest(home/name)==value['sha256'],(role,name)
   compiler=[digest(home/'build'/f'stage{n}.ll') for n in [1,2,3]];runtime=[digest(home/'build'/f'rt{n}.ll') for n in [1,2,3]]
   assert len(set(compiler))==len(set(runtime))==1
   fixed[role]={'compiler_ir':compiler,'runtime_ir':runtime}
  inputs=[Path(__file__),ROOT/'backend_tool_wrapper.py',SOURCE,OLD/'toolchain/manifest.json',ARCHIVE/'report.json',ARCHIVE/'curated.json',*bootstrap_paths.values()]
  report={'schema':2,'status':'incomplete','started_utc':stamp(),'source_identities':ids,'role_scopes':ROLE_SCOPES,'fixed_points':fixed,'bootstrap':str(args.bootstrap),'bootstrap_sha256':digest(args.bootstrap),'inputs':{str(p):digest(p) for p in inputs},'tools':{name:digest(real/name) for name in ['opt','lli','clang','llvm-as','llvm-dis']},'platform':platform.platform(),'cpu':next(x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'python':sys.version,'affinity':[0],'load_average_start':os.getloadavg(),'cases':CASES,'orders':ORDERS,'phases':{},'scope':'Six balanced rounds per case across current main, integrated candidate, and historical da84. Current main is the primary acceptance baseline; da84 is a historical source/build reference. Whole normal JIT/AOT process wall and in-process loop wall are separate; outside_loop_s includes frontend, LLVM, initialization and teardown, not pure compiler startup. All elapsed observations are new on this Intel host; historical elapsed series are not pooled. Current main and candidate tool profiles are newly measured; only the historical da84 profiles may be reused after exact input/runtime/tool/module validation. Profile observations are separately instrumented and not elapsed acceptance.','warmups':[],'oracles':{},'samples':[],'builds':{},'captures':{},'profiles':{}}
  report['inputs'].update(bootstrap_inputs)
  report['inputs'].update({row['path']:row['sha256'] for row in bootstrap_logs.values()})
  report['fresh_bootstrap_logs']=bootstrap_logs
  report['bootstrap_bindings']={role:{'record':str(bootstrap_paths[role]),'sha256':digest(bootstrap_paths[role]),'artifacts':b['artifacts']} for role,b in bootstraps.items()}
  report['bootstrap_snapshot_exclusions']={'reason':'These tracked files were outside the bootstrap snapshot selector. Each current hash is checked against its exact clean source commit blob and frozen for this measurement. All other consumed source inputs must be covered by the bootstrap before/after snapshot.','files':excluded}
  extra={Path(item['path']).resolve() for item in json.loads((OLD/'toolchain/manifest.json').read_text())['files'].values()}
  for pattern in ['libLLVM*.so*','libclang*.so*','libgc.so*']:
   extra.update(p.resolve() for p in (real.parents[1]/'x86_64-linux-gnu').glob(pattern) if p.is_file())
  report['current_tool_and_library_files']={str(p):digest(p) for p in sorted(extra)}
 else:
  report=json.loads(path.read_text());assert report['schema']==2
  assert report['source_identities']['final']['commit']==args.expected_final_commit and report['source_identities']['main']['commit']==args.expected_main_commit
  assert report['bootstrap_bindings']['main']['record']==str(args.main_bootstrap) and report['bootstrap_bindings']['final']['record']==str(args.bootstrap)
 def checkpoint():save(path,report)
 def verify():
  for k,p in HOMES.items():assert identity(p)==report['source_identities'][k],k
  for role,b in report['bootstrap_bindings'].items():
   for name,value in b['artifacts'].items():assert digest(HOMES[role]/name)==value['sha256'],(role,name)
  for p,h in report['inputs'].items():assert digest(p)==h,p
  for p,h in report['current_tool_and_library_files'].items():assert digest(p)==h,p
  for n,h in report['tools'].items():assert digest(real/n)==h,n
 envs={k:dict(clean,PYSTACHY_HOME=str(p),PYSTACHY_CACHE=str(out/(k+'-cache'))) for k,p in HOMES.items()}
 environment_keys=['PYSTACHY_HOME','PYSTACHY_CACHE','PYSTACHY_LLVM','PYTHONHASHSEED','PYTHONDONTWRITEBYTECODE','LD_LIBRARY_PATH','LIBRARY_PATH','CPATH','VALGRIND_LIB']
 current_envs={role:{key:env[key] for key in environment_keys if key in env} for role,env in envs.items()}
 if 'environments' in report:assert current_envs==report['environments']
 else:report['environments']=current_envs
 report['environment_sanitization']='All inherited PYSTACHY_ and ATTR_ options removed; set only recorded home/cache/toolchain. PYTHONPATH/PYTHONHOME removed.'
 assert args.phase not in report['phases'], 'phase already exists; preserve attempts and use a new series on changes'
 report['phases'][args.phase]={'status':'running','started_utc':stamp()};checkpoint()
 try:
  verify()
  if args.phase=='prepare':
   for role,home in HOMES.items():
    d=out/role;d.mkdir();exe=d/'mixed-text';row=execute([home/'pystachy','build',SOURCE,'-o',exe],envs[role],home,180);row.update(executable=str(exe),sha256=digest(exe));report['builds'][role]=row;checkpoint()
   for case,arguments in CASES.items():
    oracle=execute([sys.executable,SOURCE,*arguments],clean,ROOT,90,kernel=True);report['oracles'][case]=oracle
    for role,home in HOMES.items():
     for mode,cmd in [('jit',[home/'pystachy','run',SOURCE,*arguments]),('aot',[out/role/'mixed-text',*arguments])]:
      row=execute(cmd,envs[role],home,120,oracle['stdout'],True);row.update(case=case,role=role,mode=mode);report['warmups'].append(row);checkpoint()
    print('prepared',case,flush=True)
  elif args.phase=='timings':
   assert report['phases']['prepare']['status']=='passed'
   for role in HOMES:assert digest(out/role/'mixed-text')==report['builds'][role]['sha256']
   for round_no,order in enumerate(ORDERS):
    cases=list(CASES);cases=cases[round_no%3:]+cases[:round_no%3]
    for case in cases:
     for role in order:
      for mode,cmd in [('jit',[HOMES[role]/'pystachy','run',SOURCE,*CASES[case]]),('aot',[out/role/'mixed-text',*CASES[case]])]:
       row=execute(cmd,envs[role],HOMES[role],90,report['oracles'][case]['stdout'],True);row.update(round=round_no,position=order.index(role),case=case,role=role,mode=mode,load_average=os.getloadavg());report['samples'].append(row);checkpoint()
    print('round',round_no+1,'complete',len(report['samples']),'observations',flush=True)
   summary={}
   for case in CASES:
    summary[case]={}
    for mode in ['jit','aot']:
     for metric in ['wall_s','loop_s','outside_loop_s']:
      values={role:[r[metric] for r in report['samples'] if r['case']==case and r['mode']==mode and r['role']==role] for role in HOMES}
      assert all(len(v)==6 for v in values.values());meds={role:statistics.median(v) for role,v in values.items()}
      comparisons={}
      for base in ['main','da84']:
       pairs=[h/b for h,b in zip(values['final'],values[base])]
       comparisons[base]={'median_ratio':meds['final']/meds[base],'paired_ratios':pairs,'paired_median':statistics.median(pairs),'slower_pairs':sum(x>1 for x in pairs),'paired_range':[min(pairs),max(pairs)]}
      summary[case][mode+'_'+metric]={'samples':values,'medians':meds,'ranges':{k:[min(v),max(v)] for k,v in values.items()},'final_comparisons':comparisons}
   report['summary']=summary
  else:
   assert report['phases']['prepare']['status']=='passed'
   wrapper=out/'llvm';wrapper.mkdir();script=(ROOT/'backend_tool_wrapper.py').read_text().replace('#!/usr/bin/env python3','#!'+sys.executable,1)
   for tool in real.iterdir():
    p=wrapper/tool.name
    if tool.name in ['opt','lli']:p.write_text(script);p.chmod(0o755)
    else:p.symlink_to(tool)
   report['wrapper_sha256']=digest(wrapper/'opt')
   profenvs={role:dict(env,PYSTACHY_LLVM=str(wrapper),ATTR_REAL_LLVM=str(real),ATTR_VALGRIND=str(OLD/'toolchain/llvm18/usr/bin/valgrind')) for role,env in envs.items()}
   warm=out/'warm.py';warm.write_text('print(17)\n')
   for role,home in HOMES.items():execute([home/'pystachy','run',warm],profenvs[role],home,120,'17\n')
   def capture(role,stage):
    d=out/(stage+'-'+role);d.mkdir();env=dict(profenvs[role],ATTR_DIRECTORY=str(d),ATTR_STAGE=stage)
    row=execute([HOMES[role]/'pystachy','run',SOURCE,*CASES['fnmatch']],env,HOMES[role],600,report['oracles']['fnmatch']['stdout'],True)
    row['opt']=json.loads((d/'opt.json').read_text());row['lli']=json.loads((d/'lli.json').read_text())
    for tool in ['opt','lli']:assert row[tool]['returncode']==0 and row[tool]['instrumented']==(stage==tool)
    assert digest(d/'actual-input.ll')==row['opt']['input_sha256']
    assert digest(d/'optimized-output.bc')==row['opt']['output_sha256']
    assert digest(d/'runtime-fd8.so')==row['lli']['fd8']['sha256']
    assert digest(d/'input-fd9.bc')==row['lli']['fd9']['sha256']
    assert row['opt']['output_sha256']==row['lli']['fd9']['sha256']
    assert row['lli']['fd8']['sha256'] in {digest(p) for p in (out/(role+'-cache')).glob('*.so')}
    return row,d
   def bitcode_body(d,row):
    raw=subprocess.check_output([str(real/'llvm-dis'),str(d/'optimized-output.bc'),'-o','-'],env=clean,text=True)
    disassembly=(d/'optimized-output.ll') if d.is_relative_to(out) else out/('reused-'+d.name+'-optimized.ll')
    disassembly.write_text(raw)
    assert 'source_filename = '+json.dumps(row['opt']['input_path']) in raw
    body='\n'.join(x for x in raw.splitlines() if not x.startswith('; ModuleID = ') and not x.startswith('source_filename = '))+'\n'
    row['optimized_disassembly']={'path':str(disassembly),'sha256':digest(disassembly),'source_bitcode_sha256':digest(d/'optimized-output.bc'),'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'scope':'Exact llvm-dis output bound at production; body hash excludes only the checked module identifier and source-filename headers.'}
    return body
   for role in HOMES:
    row,d=capture(role,'normal');report['captures'][role]=row;bitcode_body(d,row);checkpoint();print('captured',role,flush=True)
   # Reuse only the historical da84 instruction observation, with unchanged
   # source/build identity and exact current input/runtime/tool/module controls.
   # Current main and integrated candidate each receive fresh tool profiles.
   oldrecord=json.loads((ARCHIVE/'report.json').read_text())
   assert oldrecord['status']=='complete' and all(oldrecord['phases'][stage]['status']=='passed' for stage in ['opt','lli'])
   oldcurated=json.loads((ARCHIVE/'curated.json').read_text())
   cpu_key=lambda value:re.sub(r'[^a-z0-9]','',value.lower().replace('(r)',''))
   assert cpu_key(report['cpu']) in cpu_key(oldcurated['environment']['host'])
   report['reused_profile_record']={'path':str(ARCHIVE/'report.json'),'sha256':digest(ARCHIVE/'report.json'),'cpu_host':oldcurated['environment']['host'],'tool_identity_scope':'Archived executable/manifest hashes are rechecked. Current LLVM/clang/GC shared library bytes are frozen for this series; the old profile record did not separately hash these shared libraries.'}
   manifest_path=OLD/'toolchain/manifest.json';assert digest(manifest_path)==oldrecord['input_sha256'][str(manifest_path)]
   manifest=json.loads(manifest_path.read_text())
   for item in manifest['files'].values():assert digest(item['path'])==item['sha256']
   for name,value in report['tools'].items():assert value==manifest['files'][name]['sha256'],name
   assert digest(sys.executable)==manifest['files']['python3.13']['sha256']
   report['reused_profile_toolchain_manifest_verified']=True
   def opt_args(row):
    return ['INPUT' if x==row['input_path'] else 'OUTPUT' if x==row['output_path'] else x for x in row['arguments']]
   reused={}
   for role,oldrole in [('da84','candidate')]:
    d=ARCHIVE/('normal-'+oldrole);oldopt=json.loads((d/'opt.json').read_text());oldlli=json.loads((d/'lli.json').read_text());row=report['captures'][role]
    archived=oldrecord['observations']['normal_'+oldrole]
    assert archived['opt']==oldopt and archived['lli']==oldlli
    assert all(archived[name]['returncode']==0 for name in ['execution','opt','lli'])
    assert oldrecord['native_compilers'][oldrole]['sha256']==report['source_identities'][role]['native_sha256']
    assert oldrecord['native_compilers'][oldrole]['bootstrap_record_sha256']==report['bootstrap_bindings'][role]['sha256']
    assert digest(d/'actual-input.ll')==row['opt']['input_sha256']
    assert oldlli['fd8']['sha256']==row['lli']['fd8']['sha256']
    assert oldlli['arguments']==row['lli']['arguments'] and opt_args(oldopt)==opt_args(row['opt'])
    assert bitcode_body(d,{'opt':oldopt})==bitcode_body(out/('normal-'+role),row)
    rawprofiles={}
    for stage in ['opt','lli']:
     pd=ARCHIVE/(stage+'-'+oldrole);obs=oldrecord['observations'][stage+'_'+oldrole];profile=pd/(stage+'.callgrind')
     assert all(obs[name]['returncode']==0 for name in ['execution','opt','lli'])
     assert all(obs['equivalence'][name] is True for name in ['actual_input_identical','same_flags_and_runtime_bytes','only_demonstrated_path_headers_differ'])
     assert digest(profile)==obs['profile_sha256']
     for tool in ['opt','lli']:
      assert json.loads((pd/(tool+'.json')).read_text())==obs[tool]
      assert obs[tool]['instrumented']==(stage==tool)
     assert digest(pd/'actual-input.ll')==obs['opt']['input_sha256']==row['opt']['input_sha256']
     assert digest(pd/'optimized-output.bc')==obs['opt']['output_sha256']==obs['lli']['fd9']['sha256']
     assert digest(pd/'input-fd9.bc')==obs['lli']['fd9']['sha256']
     assert digest(pd/'runtime-fd8.so')==obs['lli']['fd8']['sha256']==row['lli']['fd8']['sha256']
     assert obs['lli']['arguments']==row['lli']['arguments'] and opt_args(obs['opt'])==opt_args(row['opt'])
     assert bitcode_body(pd,obs)==bitcode_body(out/('normal-'+role),row)
     instructions=int(re.search(r'^summary: (\d+)',profile.read_text(),re.M)[1]);assert instructions==obs['attribution']['total_instructions']
     rawprofiles[stage]={'path':str(profile),'sha256':digest(profile),'instructions':instructions,'instrumented_record_and_inputs_revalidated':True}
    reused[role]={'prior_curated_sha256':digest(ARCHIVE/'curated.json'),'raw_profiles':rawprofiles,'current_capture_input_runtime_and_optimized_module_match':True,'observation_status':'reused archived instruction observation, not newly measured'}
   report['reused_baseline_profiles']=reused;checkpoint()
   for role in ['main','final']:
    report['profiles'][role]={}
    for stage in ['opt','lli']:
     row,d=capture(role,stage);normal=report['captures'][role]
     assert row['opt']['input_sha256']==normal['opt']['input_sha256'] and row['lli']['fd8']['sha256']==normal['lli']['fd8']['sha256']
     assert row['lli']['arguments']==normal['lli']['arguments'] and opt_args(row['opt'])==opt_args(normal['opt'])
     assert bitcode_body(d,row)==bitcode_body(out/('normal-'+role),normal)
     profile=d/(stage+'.callgrind');row['instructions']=int(re.search(r'^summary: (\d+)',profile.read_text(),re.M)[1]);row['profile_sha256']=digest(profile);row['normal_input_runtime_optimized_module_match']=True;row['observation_status']='newly measured tool instructions; instrumented wall time is not elapsed acceptance';report['profiles'][role][stage]=row;checkpoint();print('profiled',role,stage,row['instructions'],flush=True)
   report['instruction_comparison']={}
   for role in ['main','da84']:
    baseline=report['profiles']['main'] if role=='main' else reused[role]['raw_profiles']
    candidate=report['profiles']['final'];before=sum(x['instructions'] for x in baseline.values());after=sum(x['instructions'] for x in candidate.values())
    report['instruction_comparison'][role]={'baseline_scope':ROLE_SCOPES[role],'baseline':before,'final':after,'ratio':after/before,'scope':'Complete opt plus lli tool instructions, including lli program execution/runtime work; not a pure code-generation startup counter.','stages':{stage:{'baseline':baseline[stage]['instructions'],'final':candidate[stage]['instructions'],'ratio':candidate[stage]['instructions']/baseline[stage]['instructions']} for stage in ['opt','lli']}}
  verify();report['phases'][args.phase]['status']='passed';report['status']='complete' if all(p in report['phases'] and report['phases'][p]['status']=='passed' for p in ['prepare','timings','profile']) else 'incomplete'
 except BaseException as error:
  report['phases'][args.phase].update(status='failed',error=repr(error));report['status']='failed';raise
 finally:
  report['phases'][args.phase]['finished_utc']=stamp();report['load_average_end']=os.getloadavg();checkpoint()
if __name__=='__main__':main()
