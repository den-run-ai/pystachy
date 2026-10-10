import sys, importlib, warnings
sys.path.insert(0, sys.argv[1])
warnings.simplefilter("always")
for name in sys.argv[2:]:
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            m = importlib.import_module(name)
        ws = [f"{x.category.__name__}: {str(x.message)[:90]}" for x in w]
        r = [m.add(2, 3)]
        try: m.add(2**62, 2**62); r.append("no-ovf!")
        except OverflowError as e: r.append("OverflowError")
        def boom(x): raise ValueError(x)
        try: m.call(boom, 7); r.append("no-exc!")
        except ValueError as e: r.append(f"ValueError{e.args}")
        r.append(m.call(print, "cb-ok"))
        gil = getattr(sys, "_is_gil_enabled", lambda: "n/a")()
        print(f"{name}: OK {r} warnings={ws} gil_enabled={gil}")
    except BaseException as e:
        print(f"{name}: {type(e).__name__}: {e}")
