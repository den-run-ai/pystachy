#!/usr/bin/env python3
"""Compile independent semantic review findings; preserve raw oracle outputs."""
from pathlib import Path
import json,hashlib,time,re
P=Path('/workspace/scratch/2446eb38e476/rc2-retained-comparison')
R=json.loads((P/'results.json').read_text()); M=json.loads((P/'metadata.json').read_text()); S=json.loads((P/'summary.json').read_text())
notes={}
def note(index,category,detail,reviewer='review_open_prs'):
 notes[index]={'category':category,'finding':detail,'reviewer':reviewer,'blocker':False}
note(559,'intended_acceptance','Corrects the gen.yield payload proof: baseline rejected valid int|str yield as a %slot interpretation; candidate accepts using the generator element type. The valid regression and negative proof controls were independently validated before integration.')
for i in (603,604,605,606,607,608,611):
 note(i,'intended_acceptance','Annotation-created generic special method is deferred until global declarations and flow metadata exist. Baseline falsely rejected READY as undefined during annotation specialization; candidate accepts. Covers return, imported, PEP695, quoted, possibly-unbound, repr, or str form as named by this case. Runtime/global readiness remains checked by generated code and the focused execution tests.')
note(578,'emission_order','All 58 function bodies, top-level entities, type shapes and recursive TBAA identities are unchanged after matching string identities; early Box special methods move to the later method pass. No methods added or removed.')
note(597,'specialization_renumbering','All 17 function bodies are unchanged after exact identity matching: Bag specializations 3->2 and 7->6; Bag-1.__init__ instances 1<->2, with all call sites updated. Root list contains the same three globals in a new order. String/metadata order changes; no semantic body change.')
note(609,'definition_readiness_guard','Nine of ten bodies unchanged. Box-1.__neg__ now loads Box.def before constructing Box; false raises NameError, true keeps the same default load and constructor behavior. This is an intentional real guard insertion because the deferred method now sees declaration/flow metadata; it is not merely ordering. The new error strings and pys_raise declaration implement that guard.')
note(610,'specialization_renumbering','All 14 function bodies and all top-level entities unchanged after mapping Inner-1(int)->Inner-2 and Inner-2(str)->Inner-1. Calls, layouts and recursive TBAA follow the same mapping. Integer Inner still uses pys_new with existing allocation attributes; string Inner still uses pys_alloc.')
note(1571,'unused_method_elimination','All 63 retained functions unchanged. Six unreferenced internal mappingproxy methods are omitted: specialization1 __ror__; specialization2 __hash__, __repr__, __reversed__, __ror__, __str__. Each removed symbol occurred only at its baseline definition. Only the now-unused Dis type-description string also disappears; no remaining call target changes.')
for i,count in ((1584,28),(1590,187),(1591,270)):
 note(i,'emission_order',f'All {count} functions and top-level entities unchanged after string and recursive metadata identity matching. Function/string emission order only; no method omissions, added guards or allocation changes.')
for i,count in ((1583,17),(1586,21),(1587,21),(1588,22),(1594,15)):
 note(i,'unused_method_elimination',f'All {count} retained functions unchanged. Unused internal weakref ReferenceType-1.__hash__ and __repr__ are omitted; each baseline symbol occurred only at its definition. Associated unreachable reflection descriptors, strings and runtime declarations are removed. No remaining control-flow, global access or allocation change.')
note(1592,'unused_method_elimination','All 26 retained functions unchanged. Only unused internal weakref ReferenceType-1.__repr__ is omitted; its baseline symbol occurred only at its definition. Its unreachable reflection/string/runtime declarations also disappear. No remaining behavior change.')
for i in (1498,1499,1500,1501,1502,2432,2496):
 note(i,'unused_method_elimination','Independent complete function/top-level review found only omission of unused internal weakref ReferenceType-1.__hash__ (baseline definition was its sole reference) and the unused "weak object has gone away" string. Every retained body exactly matches with full string identity and recursive TBAA expansion; SSA/labels/calls/guards/allocations remain unchanged. No added methods or definition-readiness changes.','review_issues')
note(3066,'unchanged_rejection_context','Both compilers reject at line12 with exact core diagnostic "expected str, got int". Candidate no longer appends the annotation-specialization call context because the invalid __repr__ is checked in the later method pass. Rejection preserved; diagnostic simplification matches intended deferral.')
collection_review=json.loads(Path('/workspace/scratch/2446eb38e476/rc2-collections-ir-review.json').read_text())
closed_counts={117:48,121:16,695:41,1401:109,1402:57,1403:195,1404:442,1410:174,1411:183,1719:60}
for row in collection_review['cases']:
 i=int(row['id'])
 detail=row['explanation']+f" All {closed_counts[i]} candidate function bodies are accounted for by exact body identity after explicit symbol/class renaming and full string/TBAA identity matching. No added definition-readiness guards, unresolved direct calls, or strengthened allocation attributes."
 if i==1403:
  detail+=' Full call-graph constraint propagation confirms195 distinct baseline-to-candidate identities with zero residual changes; top-level difference is only reordering the same27 GC roots.'
 if i==1404:
  detail+=' Full call-graph closure confirms442 distinct retained bodies with zero residual changes;28 dead method bodies and2 orphan duplicate counting helpers account for30 fewer definitions.'
 if i==1411:
  detail+=' Full call-graph closure confirms all183 candidate bodies with zero residual changes:185 baseline bodies map exactly to them,16 nonmatching dead methods disappear, and2 counting-helper duplicates share candidate bodies.'
 note(i,'lazy_method_emission_and_renumbering',detail,'ci_gc_gaps + review_open_prs')



def build():
 material={r['index'] for r in R if r['classification']=='material_difference'}
 assert set(notes)==material, {'missing':sorted(material-set(notes)), 'extra':sorted(set(notes)-material)}
 rows=[]
 for r in R:
  if r['classification']=='identical': continue
  row={'index':r['index'],'case':r['case'],'classification':r['classification'], 'base_status':r['base']['status'],'candidate_status':r['candidate']['status'], 'raw_evidence_directory':r['directory']}
  if r['classification']=='path_only':
   row.update(category='checkout_prefix_only', finding='Raw outputs differ solely by exact equal-length compiler-home checkout prefix. Replacing baseline root bytes with candidate root bytes produces exact stdout, stderr and IR equality; status unchanged. No other normalization.', reviewer='exact-byte-comparison', blocker=False, substitutions=r['normalization_substitutions'])
  else: row.update(notes[r['index']])
  rows.append(row)
 result={
  'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
  'status':'complete: no unexplained differences or new rejections',
  'baseline_commit':M['source']['base']['commit'],'candidate_commit':M['source']['candidate']['commit'],
  'source':M['source'],'source_manifest_sha256':M['source_manifest_sha256'],'inventory_sha256':M['inventory_sha256'],
  'counts':S['classification_counts'],'corpus_cases':len(R),'adjudicated_raw_differences':len(rows),'material_adjudicated':len(notes),
  'new_rejections':S['new_rejections'],'new_acceptances':S['new_acceptances'],
  'infrastructure_errors':S['infrastructure_errors'],'complete_and_stable':S['complete_and_stable'],
  'compiler_self_ir':next(r for r in R if r['case']=='pystachy.py'),'runtime_ir':next(r for r in R if r['case']=='runtime.py'),
  'source_changes_during_run':S['source_changes_during_run'],'binary_changed_during_run':S['binary_changed_during_run'],
  'scope':'Native IR/status/diagnostic comparison and source-based semantic adjudication. Native JIT/AOT/GC-stressed execution is independently managed by root and is not claimed by this report. Runtime C fast-path behavior is not exercised by IR equality alone.',
  'normalization':M['normalization'],
  'supplementary_review':'Entity identity expansion and explicit specialization maps aided manual semantic review only. They did not alter raw evidence or official classifications; all 40 material differences remain classified material.',
  'cases':rows,
 }
 (P/'adjudication.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'path':str(P/'adjudication.json'),'material_adjudicated':len(notes),'raw_differences_adjudicated':len(rows),'new_rejections':S['new_rejections']}))

if __name__=='__main__': build()
