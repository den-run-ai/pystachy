"""Run the retained native parity after other heavy jobs finish; never builds."""

import json
import subprocess
from summarize import NEW, OLD, OUT, ROOT, snapshot, summarize, write_json


def main():
    if any((OUT / name).exists() for name in ('before.json', 'run.status', 'summary.json')):
        raise SystemExit('Run evidence already exists; archive it before starting another run.')
    before = snapshot()
    if before['candidate_status']:
        raise SystemExit('Candidate source checkout is dirty.')
    if len(before['ordered_corpus']) != 4579:
        raise SystemExit('Expected exactly 4579 input paths.')
    if before['candidate_inputs'] != before['baseline_inputs']:
        raise SystemExit('Common PYSTACHY_HOME is not justified: runtime/library inputs differ.')
    command = [str(OUT / 'irsame-retain.sh'), str(OLD), str(NEW)]
    environment = {'PATH': '/usr/bin:/bin', 'TMPDIR': str(OUT),
                   'PYSTACHY_HOME': str(ROOT), 'PYSTACHY_JOBS': '2'}
    write_json(OUT / 'before.json', before)
    write_json(OUT / 'command.json', {'command': command, 'cwd': str(ROOT),
                                    'environment': environment})
    print(json.dumps({'starting': command, 'log': str(OUT / 'run.log')}), flush=True)
    status = 130
    try:
        with (OUT / 'run.log').open('w') as log:
            status = subprocess.run(command, cwd=ROOT, env=environment,
                                    stdout=log, stderr=subprocess.STDOUT).returncode
    finally:
        (OUT / 'run.status').write_text(str(status) + '\n')
        write_json(OUT / 'after.json', snapshot())
    return summarize()


if __name__ == '__main__':
    raise SystemExit(main())
