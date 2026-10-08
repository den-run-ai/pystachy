# stdout is /dev/full (tests/io_keyboard_interrupt_full.full): the flush at exit fails and is
# reported, and the uncaught KeyboardInterrupt still ends the program by SIGINT
print("x")
raise KeyboardInterrupt
