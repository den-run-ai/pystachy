#!/usr/bin/env python3
"""Verify each changed accepted raw candidate module with the pinned LLVM assembler."""
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import pathlib
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=pathlib.Path)
p.add_argument('--llvm-as', required=True, type=pathlib.Path)
args = p.parse_args()
rows = [json.loads(line) for line in (args.output/'results.jsonl').read_text().splitlines()]
selected = [row for row in rows if not row['same'] and row['new']['status'] == 0]
tool = args.llvm_as.resolve()
tool_version = subprocess.check_output([str(tool), '--version'], text=True)
def one(row):
    directory = args.output/'cases'/f'{row["index"]:05d}'
    data = gzip.decompress((directory/'new.ll.gz').read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    assert digest == row['new']['ir_sha256']
    command = [str(tool), '-', '-o', '/dev/null']
    start = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        status, message = result.returncode, result.stdout
    except subprocess.TimeoutExpired as error:
        status, message, timed_out = 124, (error.stdout or b'')+b'\nLLVM verification timeout\n', True
    record = {'case':row['case'],'index':row['index'],'ir_sha256':digest,'command':command,'status':status,'timed_out':timed_out,'seconds':time.monotonic()-start}
    (directory/'new.llvm-as.msg').write_bytes(message)
    (directory/'new.llvm-as.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for record in pool.map(one, selected):
        results.append(record)
        if len(results)%100 == 0:
            print(f'Verified {len(results)}/{len(selected)} changed accepted modules',flush=True)
report = {'compiler':'candidate','tool':str(tool),'tool_sha256':hashlib.sha256(tool.read_bytes()).hexdigest(),'tool_version':tool_version,'workers':2,'expected':len(selected),'completed':len(results),'passed':sum(row['status']==0 for row in results),'failures':[row for row in results if row['status']!=0],'rows':results}
(args.output/'llvm-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ('expected','completed','passed','failures')},indent=2),flush=True)
raise SystemExit(any(row['status']!=0 for row in results))
