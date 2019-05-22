#!/usr/bin/python

import ctypes
from os import execvp
from sys import argv

# extracted from signal.h & friends, correct for x86_64 linux
SIGTERM = ctypes.c_int(15)
SIG_BLOCK = ctypes.c_int(0)
sigset_t = ctypes.c_ulong * 16
null_int = ctypes.c_int(0)

libc = ctypes.CDLL(None)

sigset = sigset_t()
libc.sigemptyset(ctypes.byref(sigset))
libc.sigaddset(ctypes.byref(sigset), SIGTERM)
libc.sigprocmask(SIG_BLOCK, ctypes.byref(sigset), null_int)

execvp(argv[1], argv[1:])
