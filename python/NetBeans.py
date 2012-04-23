# NetBeans.py

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

# NetBeans helper links:
# http://www.cs.toronto.edu/~yijun/csc408h/handouts/ExtEdProtocol.html
# http://www.cs.toronto.edu/~yijun/csc408h/handouts/tutorial2.pdf

import os
import re
import logging

log = logging.getLogger('abeans.NetBeans')

class EventStack:
  def __init__(self):
    self.events = []
  def add(self, evtFunction):
    self.events.append(evtFunction)
  def execAll(self):
    for evtFct in self.events:
      evtFct()
    self.events = []

class NetBeansCommands:
  def cmdCreate(self): pass
  def cmdSetFullName(self, bufId, filename): pass
  def cmdStartAtomic(self): pass
  def cmdEndAtomic(self): pass
  def cmdInsert(self, bufId, offset, text): pass
  def cmdSetDot(self, bufId, offset): pass
  def cmdPutBufferNumber(self, bufId, filename): pass
  def cmdInitDone(self, bufId): pass
  def cmdStopDocumentListen(self, bufId): pass
  def cmdNetbeansBuffer(self, bufId, b): pass
  def cmdEditFile(self, bufId, filename): pass
  def cmdSetReadOnly(self, bufId): pass

class NetBeansFunctions:
  def funGetCursor(self): pass

class NetBeansEvents:
  def onFileOpened(self, filename, opened, modified): pass
  def onInsert(self, bufId, offset, text): pass
  def onKilled(self, bufId): pass
  def onVersion(self, vers): pass
  def onStartupDone(self): pass
  def onDisconnect(self): pass

class NetBeansParser:
  def __init__(self, eventStack, eventsHandler, replyCallback):
    self.eventStack       = eventStack
    self.eventsHandler    = eventsHandler   # NetBeansEvents
    self.replyCallback    = replyCallback   # callback(seqId, args)

    self.reEvent          = re.compile("^(\d+):([a-zA-Z]+)=(\d+)\s*(.*)$")
    self.reReply          = re.compile("^(\d+)\s*(.*)$")

    self.reFileOpened     = re.compile("^\s*\"(.*)\"\s+([TF]+)\s+([TF]+)\s*$")
    self.reInsert         = re.compile("^\s*(\d+)\s\"(.*)\"$")
    self.reVersion        = re.compile("^\s*\"(.*)\"$")
    
    self.trueFalse = {'T': True, 'F': False}

  def parse(self, data):

    def onEvent(match):
      try:
        bufId = int(match.group(1))
        event = match.group(2)
        seqid = int(match.group(3))
        args  = match.group(4)
      except Exception as e:
        log.exception("NetBeans.parse.onEvent: exception: ")
        return False

      self.handleEvent(bufId, event, seqid, args)
      return True

    def onReply(match):
      try:
        seqid = int(match.group(1))
        args  = match.group(2)
      except Exception as e:
        log.exception("NetBeans.parse.onReply: exception: ")
        return False

      self.handleReply(seqid, args)
      return True

    matchThem = [
      (self.reEvent, onEvent),
      (self.reReply, onReply)
    ]

    ret = True

    for line in data.split("\n"):
      line = line.strip()
      if not len(line): continue

      log.debug("NetBeansParser.parse: '%s'", line)

      got = False

      for (re, callback) in matchThem:
        m = re.match(line)
        if m != None:
          if not callback(m):
            ret = False
          got = True
          break

      if not got:
        log.debug("NetBeans.parse: nothing matched for: '%s'", line)

    return ret

  def handleEvent(self, bufId, event, seqId, args):
   
    def fileOpened():
      match = self.reFileOpened.match(args)
      if match == None:
        log.error("NetBeans.handleEvent.fileOpened: unable to match args: " + args)
        return False

      filename  = match.group(1)
      opened    = self.trueFalse[match.group(2)]
      modified  = self.trueFalse[match.group(3)]

      f = lambda: self.eventsHandler.onFileOpened(filename, opened, modified)
      self.eventStack.add(f)
      return True

    def insert():
      match = self.reInsert.match(args)
      if match == None:
        log.error("NetBeans.handleEvent.insert: unable to match args: " + args)
        return False

      try:
        offset  = int(match.group(1))
        text    = match.group(2)
      except Exception as e:
        log.exception("NetBeans.handleEvent.insert: exception: ")
        return False

      # Vim is escaping double quotes when sending, we must then unescape
      text = text.replace("\\\"", "\"").replace("\\\\", "\\")

      f = lambda: self.eventsHandler.onInsert(bufId, offset, text)
      self.eventStack.add(f)
      return True

    def version():
      match = self.reVersion.match(args)
      if match == None:
        log.error("NetBeans.handleEvent.version: unable to match args: " + args)
        return False

      text = match.group(1)

      f = lambda: self.eventsHandler.onVersion(text)
      self.eventStack.add(f)
      return True

    def startupDone():
      f = lambda: self.eventsHandler.onStartupDone()
      self.eventStack.add(f)
      return True

    def killed():
      f = lambda: self.eventsHandler.onKilled(bufId)
      self.eventStack.add(f)
      return True

    def disconnect():
      f = lambda: self.eventsHandler.onDisconnect()
      self.eventStack.add(f)
      return True

    eventsParser = {
      'fileOpened'    : fileOpened,
      'insert'        : insert,
      'version'       : version,
      'startupDone'   : startupDone,
      'killed'        : killed,
      'disconnect'    : disconnect
    }

    if not eventsParser.has_key(event):
      log.debug("NetBeans.handleEvent: event not implemented: " + event)
      return True

    return eventsParser[event]()

  def handleReply(self, seqId, args):
    self.replyCallback(seqId, args)

# class NetBeans
# Provide basic NetBeans features such as:
# - commands and functions formatting and reply handling
# - basic events handling
# - buffers management
class NetBeans(NetBeansEvents, NetBeansCommands, NetBeansFunctions):

  def __init__(self):
    self.eventStack = EventStack()

    self.buffers = {}         # { id : name }
    self.replyCallbacks = {}  # { seq : callback }

    self.nextBuf = 1
    self.nextSeq = 42

    self.parser = NetBeansParser(self.eventStack, self, self.onReplyCallback)

  # public helpers

  def send(self, data):
    log.error("NetBeans.send: you must overload this method")

  def process(self, data):
    r = self.parser.parse(data)
    self.eventStack.execAll()
    return r

  # private helpers

  def onReplyCallback(self, seqId, args):
    if not self.replyCallbacks.has_key(seqId):
      #log.error("NetBeans.onReplyCallback: unknown seqId ("+str(seqId)+")")
      return False

    self.replyCallbacks[seqId](args)
    del self.replyCallbacks[seqId]

  def setReplyCallback(self, seqId, callback):
    if self.replyCallbacks.has_key(seqId):
      log.error("NetBeans.setReplyCallback: seqId ("+str(seqId)+") already set")
      return False

    self.replyCallbacks[seqId] = callback

  def getNextBuf(self):
    id = self.nextBuf
    self.nextBuf += 1
    return id

  def getNextSeq(self):
    seq = self.nextSeq
    self.nextSeq += 1
    return seq

  def formatGeneric(self, bufId, name, sign, seq, args=None):
    if args != None: args = ' ' + args
    else: args = ''
    cmd = "%d:%s%c%d%s\n" % (bufId, name, sign, seq, args)
    return cmd

  def formatCommand(self, bufId, command, args=None):
    seq = self.getNextSeq()
    cmd = self.formatGeneric(bufId, command, '!', seq, args)
    return (seq, cmd)

  def formatFunction(self, bufId, function, args=None):
    seq = self.getNextSeq()
    fun = self.formatGeneric(bufId, function, '/', seq, args)
    return (seq, fun)

  # commands and functions

  def create(self):
    bufId = self.getNextBuf()
    self.buffers[bufId] = None
    (seq, cmd) = self.formatCommand(bufId, 'create')
    self.send(cmd)
    f = lambda: self.cmdCreate()
    self.eventStack.add(f)
    return bufId

  def editFile(self, filename):
    bufId = self.getNextBuf()
    self.buffers[bufId] = filename
    (seq, cmd) = self.formatCommand(bufId, 'editFile', '"'+filename+'"')
    self.send(cmd)
    f = lambda: self.cmdEditFile(bufId, filename)
    self.eventStack.add(f)
    return bufId
    
  def setFullName(self, bufId, filename):
    self.buffers[bufId] = filename
    (seq, cmd) = self.formatCommand(bufId, 'setFullName', '"'+filename+'"')
    self.send(cmd)
    f = lambda: self.cmdSetFullName(bufId, filename)
    self.eventStack.add(f)

  def startAtomic(self):
    (seq, cmd) = self.formatCommand(0, 'startAtomic')
    self.send(cmd)
    f = lambda: self.cmdStartAtomic()
    self.eventStack.add(f)

  def endAtomic(self):
    (seq, cmd) = self.formatCommand(0, 'endAtomic')
    self.send(cmd)
    f = lambda: self.cmdEndAtomic()
    self.eventStack.add(f)

  def insert(self, bufId, offset, text):
    # Vim expect text to be sent within double quotes, we must then escape them
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    (seq, cmd) = self.formatFunction(bufId, 'insert', str(offset)+' '+'"'+text+'"')
    self.send(cmd)
    f = lambda: self.cmdInsert(bufId, offset, text)
    self.eventStack.add(f)

  def getCursor(self, callback):
    def cb(args):
      try:
        (bufId, lnum, column, offset) = args.split(' ')
        bufId = int(bufId)
        lnum = int(lnum)
        column = int(column)
        offset = int(offset)
      except:
        log.exception("NetBeans.getCursor: exception")
        return
      callback(bufId, lnum, column, offset)

    (seq, fun) = self.formatFunction(0, 'getCursor')
    self.setReplyCallback(seq, cb)
    self.send(fun)
    f = lambda: self.funGetCursor()
    self.eventStack.add(f)

  def setDot(self, bufId, offset):
    (seq, cmd) = self.formatCommand(bufId, 'setDot', str(offset))
    self.send(cmd)
    f = lambda: self.cmdSetDot(bufId, offset)
    self.eventStack.add(f)

  def putBufferNumber(self, bufId, filename):
    self.buffers[bufId] = filename
    (seq, cmd) = self.formatCommand(bufId, 'putBufferNumber', '"'+filename+'"')
    self.send(cmd)
    f = lambda: self.cmdPutBufferNumber(bufId, filename)
    self.eventStack.add(f)

  def initDone(self, bufId):
    (seq, cmd) = self.formatCommand(bufId, 'initDone')
    self.send(cmd)
    f = lambda: self.cmdInitDone(bufId)
    self.eventStack.add(f)

  def stopDocumentListen(self, bufId):
    (seq, cmd) = self.formatCommand(bufId, 'stopDocumentListen')
    self.send(cmd)
    f = lambda: self.cmdStopDocumentListen(bufId)
    self.eventStack.add(f)

  def netbeansBuffer(self, bufId, b):
    trueFalse = {True: 'T', False: 'F'}
    (seq, cmd) = self.formatCommand(bufId, 'netbeansBuffer', trueFalse[b])
    self.send(cmd)
    f = lambda: self.cmdNetbeansBuffer(bufId, b)
    self.eventStack.add(f)

  def setReadOnly(self, bufId):
    (seq, cmd) = self.formatCommand(bufId, 'setReadOnly')
    self.send(cmd)
    f = lambda: self.cmdSetReadOnly(bufId)
    self.eventStack.add(f)

  # events

  def onFileOpened(self, filename, opened, modified):
    got = False
    for fname in self.buffers.values():
      if fname == None: # create() set filename to None
        continue
      if os.path.basename(fname) == os.path.basename(filename):
        got = True
        break
    
    if not got:
      bufId = self.getNextBuf()
      self.putBufferNumber(bufId, filename)

  def onInsert(self, bufId, offset, text):
    pass

  def onKilled(self, bufId):
    if not self.buffers.has_key(bufId):
      log.warning("NetBeans.onKilled: unknown buffer "+str(bufId))
      return

    del self.buffers[bufId]

  def onVersion(self, vers):
    log.info("NetBeans.onVersion: version: " + vers)

  def onStartupDone(self):
    log.info("NetBeans.onStartupDone: startupDone")

  def onDisconnect(self):
    log.info("NetBeans.onDisconnect:")

