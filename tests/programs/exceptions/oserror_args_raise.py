# In a program without try, raise OSError(errno, text) ends it with the line of the errno's subclass.
raise EnvironmentError(17, "exists", "f")
