# (tests/ffi/run.sh runs this client without GC stress)
import resource
import evl

print(evl.serve(600))
print("peak below 200 MiB:", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024 < 200)
