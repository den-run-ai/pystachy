# stdout is /dev/full (tests/programs/io/io_keyboard_interrupt_full.full): the flush at exit fails and is
# reported, and the uncaught KeyboardInterrupt still ends the program by SIGINT
print("x")
raise KeyboardInterrupt
