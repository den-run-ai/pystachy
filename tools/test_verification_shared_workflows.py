"""Full variant/coverage jobs must validate a same-run compiler before executing it."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)


class SharedCompilerWorkflowTests(unittest.TestCase):
    def test_consumers_require_matching_producer_and_validate_before_execution(self):
        for filename, consumer, runner in (
            ('variants.yml', 'variant', 'tools/variants.sh'),
            ('coverage.yml', 'runtime', 'tools/runtime_coverage.sh'),
            ('python-versions.yml', 'python', 'tools/python_versions.sh "$TARGET" "$COMPILER" build/verify'),
            ('wasm-corpus.yml', 'corpus', 'python3 wasm/check_corpus.py --compiler "$COMPILER" --shard "$SHARD"'),
        ):
            with self.subTest(workflow=filename):
                jobs = workflow(filename)['jobs']
                producer = jobs['bootstrap']
                job = jobs[consumer]
                self.assertEqual(job['needs'], 'bootstrap')
                self.assertNotIn('if', job)  # A failed producer must skip every consumer.
                self.assertEqual(producer['runs-on'], job['runs-on'])
                self.assertEqual(producer['env']['PYSTACHY_LLVM'], job['env']['PYSTACHY_LLVM'])
                self.assertEqual(job['env']['PYSTACHY_HOME'], '${{ github.workspace }}')
                self.assertEqual(job['env']['COMPILER'], '${{ github.workspace }}/build/verify/pystachy2')
                for current in (producer, job):
                    self.assertEqual(current['env']['PYSTACHY_JOBS'], '4')
                    setup = next(s for s in current['steps'] if s.get('uses', '').startswith('actions/setup-python@'))
                    self.assertEqual(setup['with']['python-version-file'], '.python-version')
                    for step in current['steps']:
                        if step.get('uses', '').startswith('actions/checkout@'):
                            self.assertEqual(step['with']['persist-credentials'], 'false')
                        self.assertNotIn('continue-on-error', step)
                steps = producer['steps']
                verify = next(i for i, s in enumerate(steps) if s.get('run') == 'tests/verify.sh bootstrap')
                export = next(i for i, s in enumerate(steps) if s.get('run') ==
                              'python3 tools/verification_bootstrap.py export build/ci-bootstrap')
                upload = next(i for i, s in enumerate(steps) if s.get('uses', '').startswith('actions/upload-artifact@'))
                self.assertLess(verify, export)
                self.assertLess(export, upload)
                self.assertNotIn('if', steps[upload])  # Never publish a failed bootstrap.
                self.assertEqual(steps[upload]['with']['if-no-files-found'], 'error')
                steps = job['steps']
                download = next(i for i, s in enumerate(steps) if s.get('uses', '').startswith('actions/download-artifact@'))
                restore = next(i for i, s in enumerate(steps) if s.get('run') ==
                               'python3 tools/verification_bootstrap.py restore build/ci-bootstrap')
                execute = next(i for i, s in enumerate(steps) if s.get('run') == runner)
                self.assertLess(download, restore)
                self.assertLess(restore, execute)
                self.assertNotIn('if', steps[restore])
                self.assertEqual(steps[download]['with'], {
                    'name': producer['steps'][upload]['with']['name'], 'path': 'build/ci-bootstrap'})
                self.assertFalse(any('make PY=' in s.get('run', '') for s in steps))
                self.assertNotIn('PYSTACHY_CACHE', job['env'])
                self.assertNotIn('PYSTACHY_CFLAGS', job['env'])

    def test_every_variant_and_instrumented_runtime_shard_is_preserved(self):
        variant = workflow('variants.yml')['jobs']['variant']['strategy']['matrix']
        self.assertEqual(variant['variant'], ['opt-1 cflags-O0', 'opt-2', 'opt-3', 'opt-4', 'opt-5', 'opt-6'])
        self.assertEqual(variant['shard'], ['0/4', '1/4', '2/4', '3/4'])
        wasm = workflow('wasm-corpus.yml')['jobs']['corpus']['strategy']['matrix']
        self.assertEqual(wasm['shard'], ['0/4', '1/4', '2/4', '3/4'])
        coverage = workflow('coverage.yml')['jobs']
        rows = coverage['runtime']['strategy']['matrix']['include']
        self.assertEqual([(row['suites'], row['shard']) for row in rows],
                         [('corpus', f'{index}/6') for index in range(6)] + [('ffi', '')])
        hosted = coverage['hosted']['strategy']['matrix']['include']
        self.assertEqual([(row['suites'], row['shard']) for row in hosted],
                         [('corpus', f'{index}/10') for index in range(10)] + [('ffi ir', ''), ('cache unit', '')])
        self.assertNotIn('needs', coverage['hosted'])  # Hosted instrumentation stays independent.
        self.assertEqual(coverage['runtime-report']['needs'], 'runtime')
        self.assertEqual(coverage['hosted-report']['needs'], 'hosted')

    def test_other_pythons_restore_with_the_pinned_one_and_cover_every_other_minor(self):
        job = workflow('python-versions.yml')['jobs']['python']
        steps = job['steps']
        restore = next(i for i, s in enumerate(steps) if s.get('run', '').startswith('python3 tools/verification_bootstrap.py restore'))
        target = next(i for i, s in enumerate(steps) if s.get('id') == 'target')
        execute = next(i for i, s in enumerate(steps) if s.get('run', '').startswith('tools/python_versions.sh'))
        # The producer's Python restores the bootstrap; the other one is set up after it.
        self.assertLess(restore, target)
        self.assertLess(target, execute)
        self.assertEqual(steps[target]['with'], {'python-version': '${{ matrix.python }}'})
        self.assertEqual(steps[execute]['env'], {'TARGET': '${{ steps.target.outputs.python-path }}'})
        pinned = (ROOT / '.python-version').read_text().strip()
        versions = job['strategy']['matrix']['python']
        minors = {version.rstrip('t').rsplit('.', 1)[0] for version in versions}
        self.assertEqual(minors, {'3.11', '3.12', '3.14', '3.15'})
        self.assertNotIn(pinned.rsplit('.', 1)[0], minors)
        # Every free-threaded build has its GIL build beside it.
        self.assertTrue(all(version[:-1] in versions for version in versions if version.endswith('t')))

    def test_scripts_continue_to_build_private_configuration_specific_runtimes(self):
        variant = (ROOT / 'tools/variants.sh').read_text()
        self.assertIn('PYSTACHY_CACHE="$W/cache-$v" tests/run.sh "$PYS"', variant)
        self.assertIn('PYSTACHY_CFLAGS=-O0 PYSTACHY_JIT_LAUNCHER=lli', variant)
        runtime = (ROOT / 'tools/runtime_coverage.sh').read_text()
        self.assertIn('CF="-fprofile-instr-generate -fcoverage-mapping"', runtime)
        self.assertIn('PYSTACHY_CACHE=$W/cache PYSTACHY_CFLAGS=$CF LLVM_PROFILE_FILE=$W/$p/%m.profraw', runtime)


if __name__ == '__main__':
    unittest.main()
