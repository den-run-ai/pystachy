#!/usr/bin/env python3
"""Prove exact shared-runtime driver augmentation of inspected hosted LLVM.

The frozen inspect_series.py capture is valid; its unused literal-link phase
omitted the driver's target prefix and object-hook constructor. Use this separate
controller for linkage. It never executes LLVM, a compiler, or a benchmark.
"""
from pathlib import Path
import argparse
import ast
import difflib
import hashlib
import json
import re
import sys

from inspect_series import digest, git, llvm_inventory as printed_inventory, save, stamp


def llvm_inventory(path):
    inventory = printed_inventory(path)
    definitions = {}
    for printed, definition in inventory['definitions'].items():
        symbol = printed
        # llvm-dis quotes some names accepted unquoted by the source parser.
        # Join only literal ASCII names: never decode escapes or rename symbols.
        if printed.startswith('@"') and printed.endswith('"') and re.fullmatch(r'[-a-zA-Z$._][-a-zA-Z$._0-9]*', printed[2:-1]):
            symbol = '@' + printed[2:-1]
        assert symbol not in definitions, ('ambiguous symbol spelling', symbol)
        definitions[symbol] = {**definition, 'symbol': symbol, 'printed_symbol': printed}
    inventory['definitions'] = definitions
    inventory['private_symbols'] = {prefix: [symbol for symbol in definitions if symbol.startswith(prefix)] for prefix in ('@rf.', '@rp.', '@rp2.', '@rc.')}
    inventory['symbol_join_rule'] = 'Only enclosing quotes around valid plain ASCII LLVM names are removed for identity joins; printed spellings and all module bytes are retained. No escape decoding or other normalization.'
    return inventory


def literal_hooks(home):
    source = home / 'src/pystachy_compiler/lower_module.py'
    values = [ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'OBJHOOKS' for target in node.targets)]
    assert len(values) == 1 and isinstance(values[0], str)
    value = values[0].encode('ascii')
    driver = home / 'src/pystachy_compiler/driver.py'
    tree = ast.parse(driver.read_text())
    assert any(isinstance(node, ast.ImportFrom) and node.module == 'src.pystachy_compiler.lower_module'
               and any(name.name == 'OBJHOOKS' for name in node.names) for node in tree.body)
    expected = ast.dump(ast.parse("layout + ir + (OBJHOOKS if useso != '' else '')", mode='eval').body)
    writes = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute) and node.func.attr == 'write'
              and len(node.args) == 1 and ast.dump(node.args[0]) == expected]
    assert len(writes) == 1, 'current driver must contain the exact reviewed augmentation expression'
    return value, {'driver_path': str(driver), 'driver_sha256': digest(driver),
                   'write_line': writes[0].lineno, 'expression': "layout + ir + (OBJHOOKS if useso != '' else '')",
                   'hooks_source': str(source), 'hooks_source_sha256': digest(source),
                   'hooks_sha256': hashlib.sha256(value).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspection-report', type=Path, required=True)
    parser.add_argument('--backend-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inspection_path, backend_path, out = args.inspection_report.resolve(), args.backend_report.resolve(), args.output.resolve()
    assert not out.exists(), 'retain earlier linkage attempts'
    artifacts = out.with_name(out.stem + '-artifacts')
    artifacts.mkdir(exist_ok=False)
    result = {'schema': 1, 'status': 'running', 'started_utc': stamp(), 'inputs': {},
              'scope': 'Exact shared-runtime native-driver input = retained target directives + inspected ordinary-hosted module + current source OBJHOOKS. No arbitrary normalization or removal of constructor code. This linkage is not a native timing measurement.'}
    save(out, result)

    def bind(path):
        path = Path(path).resolve()
        value = digest(path)
        result['inputs'][str(path)] = value
        return value

    try:
        for path in (Path(__file__), Path(__file__).with_name('inspect_series.py'), Path(sys.executable), inspection_path, backend_path):
            bind(path)
        inspection, backend = json.loads(inspection_path.read_text()), json.loads(backend_path.read_text())
        assert inspection['status'] == backend['status'] == 'complete'
        assert backend['schema'] == 2 and backend['phases']['profile']['status'] == 'passed'
        candidate, observed = backend['source_identities']['final'], inspection['source_identity']
        assert (candidate['commit'], candidate['tree'], candidate['directory']) == (observed['commit'], observed['tree'], observed['home'])
        home = Path(candidate['directory'])
        assert git(home, 'rev-parse', 'HEAD') == candidate['commit'] and git(home, 'status', '--porcelain=v1') == ''
        for name, value in candidate['inputs'].items():
            assert observed['inputs'][name] == value and bind(home / name) == value, name
        for path, value in inspection['inputs'].items():
            assert bind(path) == value, path
        row = inspection['runs']['mixed_text/default']
        assert backend['inputs'][row['source']] == row['source_sha256']
        for path, value in row['retained_artifacts'].items():
            assert bind(path) == value, path

        control = backend['captures']['final']
        normal = backend_path.parent / 'normal-final'
        actual_path, bitcode_path = normal / 'actual-input.ll', normal / 'optimized-output.bc'
        assert bind(actual_path) == control['opt']['input_sha256']
        assert bind(bitcode_path) == control['opt']['output_sha256'] == control['lli']['fd9']['sha256']
        assert '-dlopen=/dev/fd/8' in control['lli']['arguments'], 'this proof is only for the captured shared-runtime path'
        runtime = control['lli']['fd8']
        assert runtime['regular_file'] and runtime['executable'] and runtime['elf_type'] == 3
        runtime_path = Path(runtime['path'])
        assert runtime_path.suffix == '.so'
        assert bind(runtime_path) == bind(normal / 'runtime-fd8.so') == runtime['sha256']
        cache_paths = [runtime_path.with_suffix(suffix) for suffix in ('.target', '.bc', '.o', '.so')]
        result['runtime_cache_files'] = {str(path): bind(path) for path in cache_paths}
        layout_path = runtime_path.with_suffix('.target')
        layout = layout_path.read_bytes()
        assert re.fullmatch(rb'target datalayout = "[^"\n]+"\ntarget triple = "[^"\n]+"\n', layout), 'retain exactly the two runtime target directives'
        module = Path(row['llvm']['path']).read_bytes()
        assert module.isascii(), 'the exact encoding proof here is for the retained ASCII LLVM bytes'
        hooks, source_proof = literal_hooks(home)
        result['driver_source_proof'] = source_proof
        expected = layout + module + hooks
        expected_path = artifacts / 'expected-driver-input.ll'
        expected_path.write_bytes(expected)
        (artifacts / 'target-prefix.ll').write_bytes(layout)
        (artifacts / 'object-hooks.ll').write_bytes(hooks)
        result['augmentation'] = {'layout_source': str(layout_path), 'layout_sha256': bind(layout_path),
            'layout_bytes': len(layout), 'module_sha256': row['llvm']['sha256'], 'module_bytes': len(module),
            'hooks_sha256': hashlib.sha256(hooks).hexdigest(), 'hooks_bytes': len(hooks),
            'expected_input': str(expected_path), 'expected_sha256': bind(expected_path),
            'actual_input': str(actual_path), 'actual_sha256': bind(actual_path),
            'runtime_sha256': runtime['sha256'], 'exact_match': expected == actual_path.read_bytes()}
        if not result['augmentation']['exact_match']:
            difference = artifacts / 'unexpected-input-difference.diff'
            difference.write_text(''.join(difflib.unified_diff(expected.decode('ascii').splitlines(True),
                actual_path.read_bytes().decode('latin-1').splitlines(True), fromfile='exact-driver-augmentation', tofile='actual-driver-input')))
            result['unexpected_difference'] = str(difference)
            raise AssertionError('actual driver bytes differ beyond the demonstrated target prefix and OBJHOOKS suffix')

        optimized_path = normal / 'optimized-output.ll'
        disassembly = control['optimized_disassembly']
        assert Path(disassembly['path']).resolve() == optimized_path
        assert bind(optimized_path) == disassembly['sha256']
        assert disassembly['source_bitcode_sha256'] == control['opt']['output_sha256']
        result['disassembly_production_binding'] = disassembly
        raw, optimized = llvm_inventory(actual_path), llvm_inventory(optimized_path)
        assert '@pys.obj.hooks' in raw['definitions'], 'retain the driver-added constructor in the inventory'
        result['raw_llvm'], result['optimized_llvm'] = raw, optimized
        result['constructor'] = {'symbol': '@pys.obj.hooks', 'raw': raw['definitions']['@pys.obj.hooks'],
                                 'optimized': optimized['definitions'].get('@pys.obj.hooks')}
        result['symbol_join'] = {symbol: {'raw_definition_lines': definition['raw_definition_lines'],
            'raw_printed_symbol': definition['printed_symbol'],
            'optimized_printed_symbol': optimized['definitions'].get(symbol, {}).get('printed_symbol'),
            'optimized_definition_lines': optimized['definitions'].get(symbol, {}).get('raw_definition_lines'),
            'optimized_symbol_retained': symbol in optimized['definitions']}
            for symbol, definition in raw['definitions'].items()}
        result['profiles'] = {}
        for stage in ('opt', 'lli'):
            record = backend['profiles']['final'][stage]
            path = backend_path.parent / (stage + '-final') / (stage + '.callgrind')
            assert bind(path) == record['profile_sha256'] and record['normal_input_runtime_optimized_module_match']
            result['profiles'][stage] = {'path': str(path), 'sha256': record['profile_sha256'], 'instructions': record['instructions']}
        result['instruction_comparison'] = backend['instruction_comparison']
        result['interpretation'] = 'Raw/optimized symbol line sizes are structural joins, not per-function execution costs. Complete opt+lli counts include lli program/runtime work. Optimized LLVM is the retained disassembly produced by the completed backend harness.'
        for path in artifacts.iterdir():
            bind(path)
        for path, value in result['inputs'].items():
            assert digest(path) == value, path
        result['status'] = 'complete'
    except BaseException as error:
        result.update(status='failed', error=repr(error))
        raise
    finally:
        result['finished_utc'] = stamp()
        save(out, result)


if __name__ == '__main__':
    main()
