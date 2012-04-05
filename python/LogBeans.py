# Log.py

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

import logging

def initLog(mainlogger, filename, stdout = False):
  log = logging.getLogger(mainlogger)

  FORMAT =    '%(asctime)s %(levelname)s [%(name)s] '
  FORMAT +=   '%(message)s'
  #FORMAT +=   '%(message)s (%(funcName)s(), %(filename)s:%(lineno)d)'

  formatter = logging.Formatter(fmt=FORMAT)

  handlers = []
  handlers.append(logging.FileHandler(filename))

  if stdout:
    handlers.append(logging.StreamHandler())

  for h in handlers:
    h.setFormatter(formatter)
    log.addHandler(h)

  log.setLevel(logging.DEBUG)
  log.propagate = False

def CatchAndLogException(mth):
  def methodWrapper(*args, **kwargs):
    log = logging.getLogger('abeans')
    try: mth(*args, **kwargs)
    except:
      log.exception("[ CatchAndLogException ]")

  return methodWrapper

