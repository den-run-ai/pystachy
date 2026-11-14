from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types

root = Path('/workspace/scratch/1a96cd11db0d/lean-contracts')
sys.path.insert(0, str(root / 'tools'))
import check_lean_companion as after
base = 'adac7f4c88fd86ddaecbb889042b778c701b29ed'
old = subprocess.check_output(['git', '-C', str(root), 'show', base + ':tools/check_lean_companion.py'], text=True)
before = types.ModuleType('before_companion')
exec(compile(old, base + ':tools/check_lean_companion.py', 'exec'), before.__dict__)
source = (root / 'runtime.c').read_text()
probes = [
 ('reserve_drop_last_identity',
  'memcpy(ids, l->ids, (l->len + 1) * sizeof(I)); l->ids = ids;',
  'memcpy(ids, l->ids, l->len * sizeof(I)); l->ids = ids;'),
 ('slice_shift_source_to_kind_header',
  'memcpy(r->ids + 1, l->ids + lo + 1, (hi - lo) * 8);',
  'memcpy(r->ids + 1, l->ids + lo, (hi - lo) * 8);'),
 ('reserve_atomic_companion',
  'I *ids = pys_alloc((c + 1) * sizeof(I));',
  'I *ids = pys_alloc_atomic((c + 1) * sizeof(I));'),
 ('reserve_attachment_lost',
  'memcpy(ids, l->ids, (l->len + 1) * sizeof(I)); l->ids = ids;',
  'memcpy(ids, l->ids, (l->len + 1) * sizeof(I));'),
]
declaration = 'typedef struct { I len, cap; I *a, *ids; } List;'
start = source.index(declaration)
assertion_end = '"List ABI: raw prefix and identity companion");'
end = source.index(assertion_end, start) + len(assertion_end)
header = source[start:end]
overlapping = header.replace(declaration,
    'typedef struct { I len, cap; union { I *a; I *ids; }; } List;')
overlapping = overlapping.replace('offsetof(List, ids) == 24 && sizeof(List) == 32',
                                  'offsetof(List, ids) == 16 && sizeof(List) == 24')
probes.append(('overlapping_raw_and_identity_fields', header, overlapping))
probes.append(('identity_member_macro_redirect', 'static List *list_new(I cap, int atomic) {',
               '#define ids a\nstatic List *list_new(I cap, int atomic) {'))
probes.append(('padded_raw_slot_stride', 'typedef struct { I v; } Slot;',
               'typedef struct { I padding, v; } Slot;'))
result = {'base': base, 'runtime_sha256': hashlib.sha256(source.encode()).hexdigest(),
          'baseline_adapter_sha256': hashlib.sha256(old.encode()).hexdigest(),
          'current_adapter_sha256': hashlib.sha256((root / 'tools/check_lean_companion.py').read_bytes()).hexdigest(),
          'toolchain': {'python': sys.version, 'clang': after.alias.clang_path()},
          'baseline_scope': 'The prior normalizer did not inventory reserve/slice and did not require raw/identity fields to be disjoint. Results below distinguish baseline normalized candidates from current adapter/kernel rejection; they make no baseline runtime correctness claim.',
          'cases': []}
for name, old_text, new_text in probes:
    assert old_text in source
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'runtime.c'
        changed = source.replace(old_text, new_text, 1).replace('#include "', '#include "' + str(root) + '/')
        path.write_text(changed)
        item = {'name': name, 'old': old_text, 'new': new_text,
                'before': {'normalized': True, 'candidate': before.normalize_runtime(path)}}
        try:
            candidate = after.normalize_runtime(path)
            item['after'] = {'normalized': True, 'candidate': candidate,
                             'kernel_accepted': after.checked(candidate)}
        except ValueError as error:
            item['after'] = {'normalized': False, 'error': str(error)}
        result['cases'].append(item)
out = Path('/workspace/scratch/1a96cd11db0d/companion-mutation-evidence.json')
out.write_text(json.dumps(result, indent=2) + '\n')
print(out)
print(json.dumps([{ 'name': c['name'], 'before_normalized': c['before']['normalized'], 'after': c['after'].get('error', c['after'].get('kernel_accepted')) } for c in result['cases']], indent=2))
