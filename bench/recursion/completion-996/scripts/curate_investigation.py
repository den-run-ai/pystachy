#!/usr/bin/env python3
"""Export frozen 8ca9 startup evidence without embedding raw profiles or LLVM."""
from pathlib import Path
import hashlib,json,re,statistics

ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent
MEASURED='8ca9b82c60651f746d538ad5da41ba02775bbd3c'
GUARD='b4da009aa729c7f2b8a4c9a18bb83b00d52bf17f'
LATER='860b6c503a4261a6c4dd86b803f4cf270ce95c74'
inventory={}
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def artifact(path,expected=None):
 path=Path(path).resolve();key=str(path)
 if key not in inventory:inventory[key]={'path':key,'sha256':sha(path),'bytes':path.stat().st_size}
 entry=inventory[key]
 if expected is not None:assert entry['sha256']==expected,(key,entry['sha256'],expected)
 return dict(entry)
def read(path):return json.loads(Path(path).read_text())
normal_path=ROOT/'results-8ca9/report.json';normal=read(normal_path)
assert normal['source_identities']['final']['commit']==MEASURED
assert normal['phases']['prepare']['status']==normal['phases']['profile']['status']=='passed'
assert normal['samples']==[] and 'timings' not in normal['phases']
binding_path=ROOT/'guard-source-verification/commit-binding.json';binding=read(binding_path)
verification_path=ROOT/'guard-source-verification/report.json';verification=read(verification_path)
assert binding['commit']==GUARD and binding['parent']==MEASURED
artifact(verification_path,binding['verification_report_sha256'])
assert verification['status']=='complete' and verification['source_raw_matches_measured_ablation']
preserved_dir=WORK/'experiments/final-bootstrap-v2/preserved'
preserved=read(preserved_dir/'manifest.json')
assert preserved['commit']==MEASURED and preserved['tree']==normal['source_identities']['final']['tree']
assert preserved['bootstrap_record_sha256']==normal['bootstrap_sha256']
for entry in preserved['artifacts']:
 artifact(preserved_dir/entry['preserved_as'],entry['sha256'])
for path,value in normal['inputs'].items():artifact(path,value)
for role,data in normal['bootstrap_bindings'].items():artifact(data['record'],data['sha256'])
for role,row in normal['builds'].items():artifact(row['executable'],row['sha256'])

def capture_files(directory,row):
 d=Path(directory)
 wanted={'actual-input.ll':row['opt']['input_sha256'],
         'optimized-output.bc':row['opt']['output_sha256'],
         'runtime-fd8.so':row['lli']['fd8']['sha256'],
         'input-fd9.bc':row['lli']['fd9']['sha256']}
 for name,value in wanted.items():artifact(d/name,value)
 for name in ['opt.json','lli.json','optimized-output.ll']:
  if (d/name).is_file():artifact(d/name)
 return {name:inventory[str((d/name).resolve())] for name in wanted}
captures={role:{'observation':row,'retained_files':capture_files(ROOT/'results-8ca9'/('normal-'+role),row)} for role,row in normal['captures'].items()}
profiles={}
for stage,row in normal['profiles'].items():
 d=ROOT/'results-8ca9'/(stage+'-final')
 profiles[stage]={'observation':row,'retained_files':capture_files(d,row),'profile':artifact(d/(stage+'.callgrind'),row['profile_sha256'])}
 artifact(d/(stage+'-valgrind.log'))
for role,data in normal['reused_baseline_profiles'].items():
 for stage,row in data['raw_profiles'].items():
  artifact(row['path'],row['sha256'])
  with Path(row['path']).open() as f:
   count=next(int(line.split()[1]) for line in f if line.startswith('summary: '))
  assert count==row['instructions']

totals={}
for role in ['main','da84']:
 stages={stage:normal['reused_baseline_profiles'][role]['raw_profiles'][stage]['instructions'] for stage in ['opt','lli']}
 totals[role]={'source_commit':normal['source_identities'][role]['commit'],'stages':stages,'total':sum(stages.values()),'observation_kind':'archived instruction observation revalidated against current actual-driver control'}
stages={stage:normal['profiles'][stage]['instructions'] for stage in ['opt','lli']}
totals['8ca9']={'source_commit':MEASURED,'stages':stages,'total':sum(stages.values()),'observation_kind':'new actual-driver instruction observation'}

def summarize(rows,variants):
 result={}
 for case in ['fnmatch','json','repair_scan']:
  values={name:[r['opt']['wall_s']+r['kernels'][case]['wall_s'] for r in rows if r['variant']==name] for name in variants}
  loops={name:[r['kernels'][case]['loop_s'] for r in rows if r['variant']==name] for name in variants}
  assert len(values[variants[0]])==len(values[variants[1]])
  ratios=[b/a for a,b in zip(values[variants[0]],values[variants[1]])]
  result[case]={'opt_plus_lli_sample_vectors_s':values,'loop_sample_vectors_s':loops,
                'total_medians_s':{name:statistics.median(v) for name,v in values.items()},
                'median_total_ratio':statistics.median(values[variants[1]])/statistics.median(values[variants[0]]),
                'paired_total_ratios':ratios,'paired_median_ratio':statistics.median(ratios),
                'loop_medians_s':{name:statistics.median(v) for name,v in loops.items()}}
 result['opt']={'sample_vectors_s':{name:[r['opt']['wall_s'] for r in rows if r['variant']==name] for name in variants}}
 return result

experiments={}
definitions=[('rp2_outline','outline-ablation-8ca9','outline_replay.py',['control','outlined'],
 'Remove alwaysinline only from four @rp2 child definitions; no guard/body/call-target changes.',
 'Rejected: optimized lines fell 0.95%, but fnmatch elapsed total was unchanged and JSON worsened in this diagnostic series.'),
 ('eligible_guard_outline','guard-ablation-8ca9','guard_replay.py',['control','outlined'],
 'Remove alwaysinline only from check/enter helpers on the eligible captured mixed module; ordinary inlining remains permitted.',
 'Selected for source implementation with the existing global lifetime exclusions. This does not establish performance acceptance; remaining whole-tool instructions are 10.12% above main.'),
 ('orc_lazy','lazy-ablation-8ca9','lazy_replay.py',['eager','lazy'],
 'Keep captured 8ca9 module/runtime unchanged; add -jit-kind=orc-lazy only to the lazy lli invocation.',
 'Rejected: all checksums passed, but opt+lli elapsed medians were 15.16–21.95% slower. No driver or JIT-mode source change was made.')]
for key,directory,script,variants,change,decision in definitions:
 d=ROOT/directory;r=read(d/'report.json');assert r['status']=='complete'
 assert r['input_sha256']==normal['captures']['final']['opt']['input_sha256']
 assert r['runtime_sha256']==normal['captures']['final']['lli']['fd8']['sha256']
 artifact(ROOT/script,r['script_sha256'])
 raw_inputs={name:artifact(d/(name+'.ll')) for name in variants}
 outputs=[]
 for row in r['observations']:
  rd=d/(str(row['round'])+'-'+row['variant'])
  outputs.append({'round':row['round'],'variant':row['variant'],'bitcode':artifact(rd/'prog.bc',row['bitcode_sha256']),'llvm':artifact(rd/'prog.ll')})
  assert row['opt']['returncode']==0 and all(v['returncode']==0 for v in row['kernels'].values())
  for case,obs in row['kernels'].items():assert obs['stdout']==normal['oracles'][case]['stdout']
 experiments[key]={'status':'complete_diagnostic','scope':r['scope'],'change':change,'decision':decision,
   'record':artifact(d/'report.json'),'script':artifact(ROOT/script),'tools':r['tools'],
   'source_commit':MEASURED,'actual_control_input_sha256':r['input_sha256'],'runtime_sha256':r['runtime_sha256'],
   'changed_definition_headers':r['headers'],'raw_inputs':raw_inputs,'retained_outputs':outputs,
   'variant_order':[{'round':row['round'],'variant':row['variant']} for row in r['observations']],
   'observation_count':len(r['observations']),'subprocess_count':sum(1+len(row['kernels']) for row in r['observations']),
   'all_raw_elapsed_observations':r['observations'],'summary':summarize(r['observations'],variants)}

counts_path=ROOT/'guard-ablation-8ca9/counts/report.json';counts=read(counts_path)
assert counts['status']=='complete'
artifact(normal_path,counts['baseline_report_sha256'])
artifact(ROOT/'guard-ablation-8ca9/report.json',counts['ablation_report_sha256'])
artifact(ROOT/'guard_counts.py',counts['script_sha256'])
for stage,row in counts['profiles'].items():
 artifact(counts_path.parent/(stage+'.callgrind'),row['profile_sha256'])
 artifact(counts_path.parent/(stage+'.log'))
 assert row['baseline_instructions']==normal['profiles'][stage]['instructions']
artifact(counts_path.parent/'profile.bc')
experiments['eligible_guard_outline']['instruction_confirmation']={'record':artifact(counts_path),'observations':counts['profiles'],'comparisons':counts['comparisons'],'input_sha256':counts['input_sha256'],'control_input_sha256':counts['control_input_sha256'],'runtime_sha256':counts['runtime_sha256']}
guard_total=sum(r['instructions'] for r in counts['profiles'].values())
totals['eligible_guard_ablation']={'source_commit':MEASURED,'source_patch_implementing_exact_raw_change':GUARD,'stages':{stage:row['instructions'] for stage,row in counts['profiles'].items()},'total':guard_total,'observation_kind':'raw eligible-module attribute ablation; source implementation separately verified to emit exactly these raw bytes'}
for row in totals.values():row['ratio_to_main']=row['total']/totals['main']['total']

candidate_inputs={str(Path(name).relative_to(WORK/'startup-work')):value for name,value in verification['candidate_before'].items()}
library_inputs={str(Path(name).relative_to(WORK/'pystachy')):value for name,value in verification['library_before'].items()}
source_delta={name:value for name,value in candidate_inputs.items() if library_inputs.get(name)!=value}
assert set(source_delta)=={'src/pystachy_compiler/gen.py','src/pystachy_compiler/lower_module.py','src/pystachy_compiler/program.py'}
artifact(ROOT/'verify_guards.py',verification['script_sha256'])
artifact(ROOT/'guard-source-verification/self.ll',verification['self_ir_sha256'])
artifact(ROOT/'guard-source-verification/mixed/actual-input.ll',counts['input_sha256'])
for fixture in verification['fixtures']:
 d=ROOT/'guard-source-verification'/Path(fixture['case']).name
 artifact(d/'actual-input.ll',fixture['raw_sha256']);artifact(d/'optimized-output.bc',fixture['optimized_sha256'])
 if fixture.get('aot_passed'):artifact(d/'aot',fixture['aot_sha256'])
 if fixture.get('blocked_raw_unchanged_from_base'):
  assert artifact(d/'base-raw.ll')['sha256']==artifact(d/'candidate-raw.ll')['sha256']

curated={
 'schema_version':1,
 'subject':'Pystachy PR 996: frozen 8ca9 actual-driver startup evidence and follow-up diagnostics',
 'status':'complete_export; normal-driver elapsed acceptance series was not started',
 'measured_source_commit':MEASURED,
 'verified_guard_patch_commit':GUARD,
 'later_published_candidate':{'commit':LATER,'tree':'98d8ee9dea118a2cf3276defa3c4f6ccec126c78','included_in_these_measurements':False,'state_at_export':'fresh bootstrap and final measurement pending; do not attribute 8ca9 or raw-ablation results to this candidate'},
 'environment':{key:normal[key] for key in ['platform','cpu','python','affinity','environments','environment_sanitization','tools','current_tool_and_library_files','load_average_start','load_average_end']},
 'provenance':{'normal_record':artifact(normal_path),'source_identities':normal['source_identities'],'path_scope':'Directory paths identify measurement-time locations; the active worktree may subsequently advance. Commit/input hashes and retained captures identify this frozen series.','fixed_points':normal['fixed_points'],'bootstrap_bindings':normal['bootstrap_bindings'],'bootstrap_snapshot_exclusions':normal['bootstrap_snapshot_exclusions'],'input_files':normal['inputs'],'preserved_8ca9':{'manifest':artifact(preserved_dir/'manifest.json'),'contents':preserved},'reused_profile_record':normal['reused_profile_record'],'reused_profile_toolchain_manifest_verified':normal['reused_profile_toolchain_manifest_verified'],'reused_baseline_profiles':normal['reused_baseline_profiles']},
 'normal_pipeline':{'phases':normal['phases'],'cases':normal['cases'],'planned_balanced_orders':normal['orders'],'exact_normal_captures':captures,'instrumented_captures':profiles,'instruction_totals':totals,'instruction_comparisons':normal['instruction_comparison'],'main_control_has_guard_helpers':'@pys.recursion.' in (ROOT/'results-8ca9/normal-main/actual-input.ll').read_text()},
 'all_normal_series_elapsed_observations':{'aot_preparation_builds':normal['builds'],'cpython_oracles':normal['oracles'],'preparation_warmups':normal['warmups'],'balanced_driver_samples':normal['samples'],'balanced_driver_status':'not started: root redirected work after the profile/CI evidence showed a remaining startup regression','classification':'Preparation builds and warmups are not elapsed acceptance samples. First JIT warmups use fresh private caches and may include runtime compilation. Capture/profile process and tool wall times are retained in exact_normal_captures/instrumented_captures above. Instrumented wall times are diagnostic only.'},
 'experiments':experiments,
 'source_verification':{'record':artifact(verification_path),'commit_binding':{'file':artifact(binding_path),'contents':binding},'mode':verification['scope'],'compiler_source_hash_delta_from_8ca9':source_delta,'full_consumed_input_manifests':'candidate_before and library_before in the hashed verification record','self_ir_sha256':verification['self_ir_sha256'],'all_execution_observations':verification['rows'],'fixtures':verification['fixtures'],'source_raw_matches_measured_ablation':verification['source_raw_matches_measured_ablation'],'source_change':'Capture the existing recursion_blocked lifetime policy before optimization/EH, pass it explicitly to module lowering, and retain mandatory check/enter inlining only for excluded programs. Scalar helpers, guard semantics, effects and cold overflow paths are unchanged.'},
 'limitations':[
  'Performance acceptance remains open for the later combined candidate; no six-round normal-driver timing series was run at 8ca9.',
  'Main has no recursion guard helpers. Its total is not an out-of-line guarded baseline; these common-workload comparisons include the added guard implementation cost.',
  'Whole opt+lli instructions count complete tool processes. lli includes JIT compilation, executed program/runtime/GC work and teardown; it is not a pure code-generation startup count.',
  'Raw ablations bypass the native frontend and change only the explicitly recorded attributes or lli mode. They are not normal-driver acceptance series.',
  'Raw elapsed samples were interleaved on CPU 0, but this is a shared Intel host. Short-loop kernel differences remain noisy; no sample was discarded.',
  'ORC-lazy loop timestamps can include work at first use and must not be described as steady-state kernel timings. The probe is not broad exception/generator/GC/lifecycle validation.',
  'Main/da84 instruction observations are explicitly reused historical counts, after current actual-driver captures and archived profile hashes/counts/inputs/flags/runtime/optimized bodies were revalidated.',
  'The archived tool manifest did not independently hash LLVM/clang shared libraries. Current-series library bytes are frozen; the historical omission is retained, not retroactively repaired.',
  'Only demonstrated LLVM ModuleID/source_filename path headers were omitted for the stated optimized-body equivalence checks. Raw source-module equality for the selected guard patch was literal.',
  'Hosted self-compilation and native program fixture execution are not a native compiler fixed-point bootstrap claim for the guard patch.',
  'Profile-wrapper cache warmup execution times were not retained as measurement samples. All retained measurement/capture/profile/replay and source-verification elapsed observations are included here.',
  'The older missing recursion-region-startup-diagnostics.json from the handoff is outside this export and is not claimed to be recovered.'
 ],
 'reproduction':{'notes':artifact(ROOT/'curated-8ca9-investigation-repro.txt'),'scripts':{name:artifact(ROOT/name) for name in ['measure.py','backend_tool_wrapper.py','outline_replay.py','guard_replay.py','guard_counts.py','lazy_replay.py','verify_guards.py','curate_investigation.py']},'raw_artifact_policy':'Large raw files remain at the listed local paths. This export embeds their identities, not their contents; no raw Callgrind text is embedded.'},
}
curated['retained_raw_artifact_inventory']=list(inventory.values())
encoded=json.dumps(curated,indent=2,ensure_ascii=True)+'\n'
assert not re.search(r'https?://',encoded),'unexpected URL in selected evidence fields'
path=ROOT/'curated-8ca9-investigation.json';path.write_text(encoded)
print(json.dumps({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'retained_artifacts':len(inventory),'whole_tool_instruction_totals':{name:row['total'] for name,row in totals.items()},'raw_experiment_subprocesses':{name:row['subprocess_count'] for name,row in experiments.items()},'normal_elapsed_samples':len(normal['samples'])},indent=2))
