"""Fresh actual ORC/AOT Callgrind counts with checked collection boundaries."""
import re
from pathlib import Path
import replay_support as replay

COUNTS = {"json_calls": 2000, "json_file_calls": 2000}

def collect(out, result, variants, envs, environment, run, save):
    llvm = Path(result["tools"]["llvm"])
    vg = Path(result["tools"]["valgrind_root"])
    python = result["tools"]["python"]
    source = out / "count_control.c"
    source.write_text("#include <valgrind/callgrind.h>\nvoid count_start(void) { CALLGRIND_TOGGLE_COLLECT; }\nvoid count_stop(void) { CALLGRIND_TOGGLE_COLLECT; }\n")
    library = out / "libcount_control.so"
    run([llvm / "clang", "-O2", "-shared", "-fPIC", "-I" + str(vg / "include"), source, "-o", library], out, environment)
    result["count_control"] = {"source_sha256": replay.digest(source), "library_sha256": replay.digest(library)}
    wrapper = out / "count-llvm"
    wrapper.mkdir()
    for path in llvm.iterdir():
        if path.name != "lli":
            (wrapper / path.name).symlink_to(path)
    script = wrapper / "lli"
    script.write_text('#!/bin/sh\nexec "' + str(vg / "bin/valgrind") + '" --tool=callgrind --error-exitcode=99 --collect-atstart=no --callgrind-out-file="$COUNT_PROFILE" "' + str(llvm / "lli") + '" "$@"\n')
    script.chmod(0o755)
    def bodies(text):
        return {match[1]: match[0] for match in re.finditer(r"^define [^\n]*?@([^ (]+)\([^\n]*\).*?^}", text, re.M | re.S)}
    for case, n in COUNTS.items():
        if case not in result["changed_cases"]:
            continue
        data = result["cases"][case]
        original_source = Path(data["source"])
        text = original_source.read_text()
        altered = ('import ffi\n\n@ffi.extern(' + repr(str(library)) + ')\ndef count_start() -> None: ...\n\n@ffi.extern(' + repr(str(library)) + ')\ndef count_stop() -> None: ...\n\n' + text)
        altered = altered.replace('print("warm", kernel(text, n))', 'count_start()\nwarm = kernel(text, n)\ncount_stop()\nprint("warm", warm)')
        altered = altered.replace('    result = kernel(text, n)', '    count_start()\n    result = kernel(text, n)\n    count_stop()')
        marked = out / (case + "-count.py")
        marked.write_text(altered)
        oracle = replay.parse(run([python, original_source, n, *data["extra_args"]], out, environment))
        counts = {"n": n, "checksum": oracle["checksum"], "instrumented_source_sha256": replay.digest(marked), "variants": {}}
        data["instruction_counts"] = counts
        for name, home in variants.items():
            native = result["native_compilers"][name]["path"]
            raw = out / (name + "-" + case + ".ll")
            executable = out / (name + "-" + case)
            assert replay.digest(raw) == data["frontend_ir"][name]["sha256"]
            assert replay.digest(executable) == data["builds"][name]["sha256"]
            marked_ir = out / (name + "-" + case + "-count.ll")
            run([native, "ir", marked, "-o", marked_ir], home, envs[name])
            before, after = bodies(raw.read_text()), bodies(marked_ir.read_text())
            assert "f.kernel" in before
            assert all(key in after and value == after[key] for key, value in before.items() if key != "main.init"), (name, case, "instrumentation changed a function body")
            counts["variants"][name] = {}
            for mode in ("jit", "aot"):
                profile = out / (name + "-" + case + "-" + mode + ".callgrind")
                environment_for_count = dict(envs[name], COUNT_PROFILE=str(profile))
                markers = mode == "jit"
                if mode == "jit":
                    environment_for_count["PYSTACHY_LLVM"] = str(wrapper)
                    environment_for_count["PYSTACHY_CACHE"] = str(out / (name + "-count-cache"))
                    command = [native, "run", marked, n, *data["extra_args"]]
                else:
                    symbols = run([llvm / "llvm-nm", executable], home, environment_for_count)["stdout"]
                    markers = not any(line.split() and line.split()[-1] == "f.kernel" for line in symbols.splitlines())
                    target = executable
                    if markers:
                        target = out / (name + "-" + case + "-count")
                        run([native, "build", marked, "-o", target], home, envs[name])
                    command = [vg / "bin/valgrind", "--tool=callgrind", "--error-exitcode=99", "--collect-atstart=no"]
                    if not markers:
                        command += ["--toggle-collect=f.kernel", "--dump-after=f.kernel"]
                    command += ["--callgrind-out-file=" + str(profile), target, n, *data["extra_args"]]
                row = replay.parse(run(command, home, environment_for_count, 360), counts["checksum"])
                replay.save_json(out / (name + "-" + case + "-" + mode + "-count-attempt.json"), row)
                profiles = [profile]
                if mode == "aot" and not markers:
                    parts = sorted(out.glob(profile.name + ".*"))
                    assert len(parts) == 8, (name, case, "expected eight kernel returns", len(parts))
                    profiles += parts
                    row["verified_kernel_returns"] = len(parts)
                row["instructions"] = sum(int(re.search(r"^summary: (\d+)", path.read_text(), re.M)[1]) for path in profiles)
                assert row["instructions"] > n
                row.update(instructions_per_kernel_call=row["instructions"] / 8, profile_sha256={path.name: replay.digest(path) for path in profiles},
                           all_non_entry_function_bodies_identical=True, aot_original_kernel_symbol_absent=markers if mode == "aot" else None,
                           scope="eight kernel calls, including warm-up; runtime/GC included; compiler/timers/printing excluded",
                           collection="client markers" if markers else "unmodified AOT f.kernel entry/return")
                counts["variants"][name][mode] = row
                save()
                print("counted", case, name, mode, row["instructions"], flush=True)
