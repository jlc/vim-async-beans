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

# TODO: part of ensime-common/src/main/python/Helper.py

#
# Simple Singleton decorator
#
# Be carefull: does not call parents initialization
def SimpleSingleton(cls):
  instances = {}
  def instance():
    if cls not in instances:
      instances[cls] = cls()
    return instances[cls]
  return instance

@SimpleSingleton
class LogSetup:

  FORMAT = '%(asctime)s %(levelname)s [%(name)s] %(message)s' # (%(funcName)s(), %(filename)s:%(lineno)d)'

  def __init__(self):
    self.handlers = {} # {name: handler}

  def setup(self, loggerName, logFilename = None, stdout = False):
    self.initLogger(loggerName)

    if logFilename != None and logFilename != '':
      self.addFileHandler(loggerName, logFilename)
    else:
      self.removeFileHandler(loggerName)

    if stdout:
      self.addStreamHandler(loggerName)
    else:
      self.removeStreamHandler(loggerName)

  def loggerNames(self):
    for name in self.handlers.keys():
      yield name

  def hasLogger(self):
    if len(self.handlers) > 0: return True
    return False

  def initLogger(self, name):
    log = logging.getLogger(name)

    if not self.handlers.has_key(name):
      self.handlers[name] = {}

      log.setLevel(logging.DEBUG)
      log.propagate = False

  def addHandler(self, loggerName, handlerName, handlerCreator):
    if self.handlers.has_key(loggerName) and not self.handlers[loggerName].has_key(handlerName):
      try:
        handler = handlerCreator()
        handler.setFormatter(logging.Formatter(fmt=self.FORMAT))
        self.handlers[loggerName][handlerName] = handler

        logging.getLogger(loggerName).addHandler(handler)
      except Exception as e:
        print("LogSetup.addHandler: exception while adding handler '%s' for logger '%s': %s" % (handlerName, loggerName, str(e)))

  def removeHandler(self, loggerName, handlerName):
    if self.handlers.has_key(loggerName) and self.handlers[loggerName].has_key(handlerName):
      logging.getLogger(loggerName).removeHandler(self.handlers[loggerName][handlerName])
      del self.handlers[loggerName][handlerName]

  def addStreamHandler(self, loggerName):
    self.addHandler(loggerName, 'streamHandler', lambda: logging.StreamHandler())

  def removeStreamHandler(self, loggerName):
    self.removeHandler(loggerName, 'streamHandler')

  def addFileHandler(self, loggerName, logFilename):
    self.addHandler(loggerName, 'fileHandler', lambda: logging.FileHandler(logFilename))

  def removeFileHandler(self, loggerName):
    self.removeHandler(loggerName, 'fileHandler')


def CatchAndLogException(mth):
  def methodWrapper(*args, **kwargs):
    # forward exception on all registered loggers or use a basic configuration
    if LogSetup().hasLogger():
      logs = [logging.getLogger(name) for name in LogSetup().loggerNames()]
    else:
      logging.basicConfig()
      logs = [logging.getLogger()]
    try:
      return mth(*args, **kwargs)
    except:
      for log in logs:
        log.exception("[ CatchAndLogException ]")

  return methodWrapper

