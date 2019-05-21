#!/usr/bin/python

import signal
from os import execv
from sys import argv

signal.signal(signal.SIGTERM, signal.SIG_IGN)
execv("/usr/local/bin/uwsgi", argv)
