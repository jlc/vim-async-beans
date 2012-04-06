#!/usr/bin/python

# Copyright 2012 Jeanluc Chasseriau <jeanluc@lo.cx>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
import os
import sys
sys.path.append(os.path.dirname(sys.argv[0])+"/../python")
from LogBeans import *

DEFAULT_LOG_NAME = 'TestPingProc'
DEFAULT_LOG_FILENAME = DEFAULT_LOG_NAME + '.log'

initLog('', DEFAULT_LOG_FILENAME)

log = logging.getLogger('TestPingProc')

def main():

  i = 0
  output = "pinger.out"

  extra = '' # 'o'*8

  while( i < 5 ):
    l = raw_input()
    log.debug("raw_input: '%s'", l)
    print "%d - pong: %s - %s" % (i,l.strip(),extra)
    i += 1
    time.sleep(1)

  log.debug("done")
  return 0

if __name__ == '__main__':
  main()

