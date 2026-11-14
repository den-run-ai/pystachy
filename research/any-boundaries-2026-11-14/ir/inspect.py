"""Summarize retained IR audit evidence without changing raw inputs.

By default no LLVM text is normalized. --home-pair adds an auxiliary comparison
that changes ONLY exact differing home prefixes in recognized generated module
location constants. Every changed line is retained for independent review.
"""
import argparse, collections, hashlib, json, re
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('audit',type=Path)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--expected-cases',type=Path,required=True)
p.add_argument('--home-pair',nargs=2)
a=p.parse_args()
counts=collections.Counter()
rows=[]
locations=[]
prefixes=tuple(x.encode() for x in a.home_pair) if a.home_pair else ()
if prefixes:
    assert len(prefixes[0]) == len(prefixes[1])

def norm_ir(data, prefix, case, side):
    result=[]
    for number, line in enumerate(data.splitlines(keepends=True),1):
        if prefix not in line:
            result.append(line); continue
        # Generated ImportError module-source suffix. Leave all other payloads
        # untouched pending a separate explanation, including arbitrary literals.
        allowed = (line.startswith(b'@s.') and b' = private unnamed_addr global ' in line
                   and b'c"cannot import name ' in line
                   and re.search(rb" from '[^']+' \("+re.escape(prefix)+rb'/lib/[A-Za-z0-9_./-]+\.py\)\\00"\}, align 8\s*$',line))
        # gen_modattr(sys.prefix/base_prefix) emits the exact compiler home.
        # lib/gettext.py's default locale directory consumes sys.base_prefix.
        bare = (line.startswith(b'@s.') and b' = private unnamed_addr global ' in line
                and re.search(rb' c"'+re.escape(prefix)+rb'\\00"\}, align 8\s*$',line))
        allowed = allowed or bare
        locations.append({'case':case,'side':side,'line':number,'allowed':bool(allowed),'text':line.decode().rstrip()})
        result.append(line.replace(prefix,prefixes[0]) if allowed else line)
    return b''.join(result)

def norm_msg(data, prefix):
    # Exact source-location shapes, manually reviewed after the shell oracle
    # conservatively refused prose containing possessive apostrophes.
    home=re.escape(prefix)+rb'/lib/'
    loc=rb'[A-Za-z0-9_./-]+\.py:[0-9]+'
    data=re.sub(rb'^'+home+rb'('+loc+rb': error:)',lambda m:prefixes[0]+b'/lib/'+m[1],data,flags=re.M)
    data=re.sub(rb'(for the call at )'+home+rb'('+loc+rb')',lambda m:m[1]+prefixes[0]+b'/lib/'+m[2],data)
    return re.sub(rb'(<function [^\n]*? \()'+home+rb'('+loc+rb'\)>)',lambda m:m[1]+prefixes[0]+b'/lib/'+m[2],data)

for d in sorted((x for x in a.audit.iterdir() if x.is_dir() and x.name.isdigit()),key=lambda x:int(x.name)):
    case=(d/'case').read_text().strip() if (d/'case').exists() else '<missing>'
    row={'number':int(d.name),'case':case,'directory':str(d)}
    if not all((d/x).exists() for x in ('old.status','new.status','report')):
        row['category']='incomplete'; rows.append(row); counts[row['category']]+=1; continue
    old=int((d/'old.status').read_text()); new=int((d/'new.status').read_text())
    row.update(old_status=old,new_status=new,
               source_sha256=(d/'source.sha256').read_text().split()[0],
               mode=(d/'mode').read_text().strip())
    for side in ('old','new'):
        row[side+'_ir_sha256']=(d/(side+'.ir.sha256')).read_text().split()[0]
        row[side+'_msg_sha256']=(d/(side+'.msg.sha256')).read_text().split()[0]
        row[side+'_ir_bytes']=int((d/(side+'.ir.bytes')).read_text())
    if old==0 and new!=0: category='new_rejection'
    elif old!=0 and new==0: category='new_acceptance'
    elif old!=new: category='status_change'
    elif not (d/'report').stat().st_size: category='identical'
    else:
        oldmsg=(d/('old.normal.msg' if (d/'old.normal.msg').exists() else 'old.msg')).read_bytes()
        newmsg=(d/('new.normal.msg' if (d/'new.normal.msg').exists() else 'new.msg')).read_bytes()
        oldpath=d/'old.ll'; newpath=d/'new.ll'
        message_home_only = oldmsg!=newmsg and prefixes and norm_msg(oldmsg,prefixes[0])==norm_msg(newmsg,prefixes[1])
        if oldmsg!=newmsg and not message_home_only:
            category='diagnostic_change'
        elif oldpath.exists()!=newpath.exists(): category='ir_presence_change'
        elif oldpath.exists():
            oldir=oldpath.read_bytes(); newir=newpath.read_bytes()
            row.update(old_ir_sha256=hashlib.sha256(oldir).hexdigest(),new_ir_sha256=hashlib.sha256(newir).hexdigest())
            normold=norm_ir(oldir,prefixes[0],case,'old') if prefixes else oldir
            normnew=norm_ir(newir,prefixes[1],case,'new') if prefixes else newir
            if normold==normnew: category='generated_home_only'
            else:
                category='ir_change'
                if prefixes:
                    (d/'old.location-normalized.ll').write_bytes(normold)
                    (d/'new.location-normalized.ll').write_bytes(normnew)
        elif message_home_only: category='diagnostic_home_only'
        else: category='other_change'
    if category == 'diagnostic_change':
        row['old_diagnostic'] = (d/'old.msg').read_text()
        row['new_diagnostic'] = (d/'new.msg').read_text()
    if category == 'ir_change':
        def functions(data):
            out = {}; name = None; body = []
            for line in data.decode().splitlines(keepends=True):
                match = re.match(r'define[^@]*@([^\n(]+)\(', line)
                if match:
                    name = match[1]; body = [line]
                elif name is not None:
                    body.append(line)
                    if line.strip() == '}':
                        out[name] = ''.join(body); name = None
            return out
        old_functions, new_functions = functions(normold), functions(normnew)
        row['changed_functions'] = sorted(name for name in old_functions.keys() | new_functions.keys()
                                          if old_functions.get(name) != new_functions.get(name))
        row['added_functions'] = sorted(new_functions.keys() - old_functions.keys())
        row['removed_functions'] = sorted(old_functions.keys() - new_functions.keys())
    row['category']=category
    rows.append(row); counts[category]+=1
expected=a.expected_cases.read_text().splitlines()
assert len(expected)==len(set(expected)), 'duplicate expected cases'
assert [r['case'] for r in rows]==expected, 'missing, reordered or unexpected audit case'
assert [r['number'] for r in rows]==list(range(1,len(expected)+1)), 'missing case directory'
result={'audit':str(a.audit),'home_pair':a.home_pair,'expected_cases':str(a.expected_cases),'counts':dict(counts),'total':len(rows),'cases':rows,'location_substitutions':locations}
a.output.write_text(json.dumps(result,indent=2)+'\n')
a.output.with_suffix('.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
print(json.dumps({'audit':str(a.audit),'counts':dict(counts),'total':len(rows),'unrecognized_home_occurrences':sum(not r['allowed'] for r in locations)},indent=2))
for r in rows:
    if r['category'] not in ('identical','generated_home_only','diagnostic_home_only'):
        print(r['category'],r['case'],r.get('old_status'),r.get('new_status'),r['directory'])
