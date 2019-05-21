#!/usr/bin/python

import signal
from os import execvp
from sys import argv

signal.signal(signal.SIGTERM, signal.SIG_IGN)
execvp(argv[1], argv[1:])
