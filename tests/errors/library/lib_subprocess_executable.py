# error: run() got an unexpected keyword argument 'executable'
# The program is args[0]. Of Popen's parameters there are no executable, preexec_fn, pass_fds,
# user, group, extra_groups, umask, pipesize and process_group.
import subprocess

print(subprocess.run(["-c", "exit 0"], executable="/bin/sh").returncode)
