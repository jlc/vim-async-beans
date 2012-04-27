#!/usr/bin/python

# VimProcRunner.py

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

import sys
import os
import pty
import re
import socket
import select
import termios
import tty
from optparse import OptionParser

from NetBeans import *
from LogBeans import *

DEFAULT_LOG_NAME = 'VimProcRunner'
DEFAULT_LOG_FILENAME = DEFAULT_LOG_NAME + '.log'

DEFAULT_PROXY_IN_FILENAME = 'vim-async-beans.in'
DEFAULT_PROXY_OUT_FILENAME = 'vim-async-beans.out'

DEFAULT_NETBEANS_INTERFACE = 'localhost'
DEFAULT_NETBEANS_PORT = 60101

log = logging.getLogger('VimProcRunner')

class Proxy:

  class Handler:
    def fromVim(self, data): pass
    def fromProc(self, desc, data): pass

  # Simple line buffer: TODO: may contain several lines
  class LineBuffer:
    def __init__(self):
      self.buf = ''
    def add(self, data, readyFct):
      self.buf += data

      flag = True
      while flag:
        n = self.buf.find("\n")

        if n == -1:
          flag = False
        else:
          l = self.buf[:n].strip()
          self.buf = self.buf[n+1:]
          if len(l) > 0:
            readyFct(l)

  def __init__(self, vimDesc, handler):
    self.handler    = handler

    self.vimDesc    = vimDesc

    self.procDescs  = [] # list of desc

    self.vimBuffer  = Proxy.LineBuffer()
    self.procBuffers = {} # { desc : Proxy.LineBuffer }

    self.flagContinue = False

  def stop(self):
    self.flagContinue = False

  def addProc(self, desc):
    self.procDescs.append(desc)
    self.procBuffers[desc] = Proxy.LineBuffer()

  def removeProc(self, desc):
    descs = []
    for d in self.procDescs:
      if d == desc: continue
      descs.append(d)
    self.procDescs = descs
    del self.procBuffers[desc]

  def readFromVim(self, desc):
    try: data = self.vimDesc.recv(4096)
    except:
      log.exception("Proxy.readFromVim: exception")
      return False

    def ok(data):
      self.handler.fromVim(data)

    self.vimBuffer.add(data, ok)
    return True

  def readFromProc(self, desc):
    try: data = os.read(desc, 4096)
    except:
      log.exception("Proxy.readFromProc: exception")
      return False

    def ok(data):
      self.handler.fromProc(desc, data)

    self.procBuffers[desc].add(data, ok)
    return True

  def run(self):

    def vimError():
      log.error("Proxy.run: error reading from vim")
      return False

    def procError(desc):
      log.error("Proxy.run: error reading from process")
      return False

    output = []
    timeout = 0.1 # sec

    log.debug("Start running proxy")

    self.flagContinue = True

    while self.flagContinue:

      input = [self.vimDesc]
      input.extend(self.procDescs)
      error = [self.vimDesc]
      error.extend(self.procDescs)

      inputHandlers = {self.vimDesc: self.readFromVim}
      errorHandlers = {self.vimDesc: vimError}

      for desc in self.procDescs:
        inputHandlers[desc] = self.readFromProc
        errorHandlers[desc] = procError
      
      try:
        (i, o, e) = select.select(input, output, error, timeout)
      except:
        log.exception("Proxy.run: interrupted while selecting")
        self.flagContinue = False
        continue

      for ii in i:
        if not inputHandlers[ii](ii):
          self.flagContinue = False

      for ee in e:
        if not errorHandlers[ee](ee):
          self.flagContinue = False

# class ProcRunner
# Specific to vim async, provide insert data handling and buffering
class ProcRunner(NetBeans, Proxy.Handler):

  def __init__(self, main, vimSocket):
    NetBeans.__init__(self)

    self.vimSocket            = vimSocket

    self.processes            = {} # { id : desc }
    self.invProcesses         = {} # { desc : id }

    self.vimProxyInId         = 0
    self.vimProxyInFilename   = DEFAULT_PROXY_IN_FILENAME
    self.vimProxyOutId        = 0
    self.vimProxyOutFilename  = DEFAULT_PROXY_OUT_FILENAME

    self.main                 = main
    self.buffersInserts       = {}  # { id : [insert1, insert2, ...] }

    self.reProtoExecCmd     = re.compile("^##_EXEC_(\d+)_\[(.*)\]_##$")
    self.reProtoKillCmd     = re.compile("^##_KILL_(\d+)_##$")
    self.reProtoDataCmd     = re.compile("^##_DATA_(\d+)_##(.*)$")
    self.reProtoDataAndPauseCmd     = re.compile("^##_DATA_(\d+)_AND_PAUSE_AFTER_(\d+)_##(.*)$")
    self.reProtoPauseCmd    = re.compile("^##_PAUSE_##$")
    self.reProtoContinueCmd = re.compile("^##_CONTINUE_##$")
    self.protoStarted       = "##_STARTED_%d_##"
    self.protoTerminated    = "##_TERMINATED_%d_##"
    self.protoData          = "##_DATA_%d_##%s"

    self.isPause            = False
    self.pausedMessages     = []
    self.pauseAfter         = 0 # nb messages to count before pausing
    self.pauseAfterProcId   = 0 # id of the process to count message from

  def hasInsert(self, bufId):
    if not self.buffersInserts.has_key(bufId):
      return False
    if not len(self.buffersInserts[bufId]):
      return False
    return True

  def getLastInsert(self, bufId):
    if not self.buffersInserts.has_key(bufId):
      return None
    if not len(self.buffersInserts[bufId]):
      return None

    self.buffersInserts[bufId].reverse()
    insert = self.buffersInserts[bufId].pop()
    self.buffersInserts[bufId].reverse()
    return insert

  def pauseVimMessages(self, after=0, procId=0):
    log.debug("ProcRunner.pauseVimMessages: pausing")
    if after > 0:
      self.pauseAfter = after
      self.pauseAfterProcId = procId
    else:
      self.isPause = True

  def continueVimMessages(self):
    log.debug("ProcRunner.continueVimMessages: continuing")
    self.isPause = False

    for msg in self.pausedMessages:
      self.sendToVim(msg)

    self.pausedMessages = []

  def setupInOutBuffers(self):
    # note: when using create(), buffer ids are killed and reopened by vim
    # weirdly, initial ids are still used by vim later on
    # editFile() is more reliable
    self.vimProxyInId = self.editFile(self.vimProxyInFilename)
    self.setReadOnly(self.vimProxyInId)
    self.stopDocumentListen(self.vimProxyInId)

    self.vimProxyOutId = self.editFile(self.vimProxyOutFilename)

    # create an empty buffer and thus allow hidding the previous ones
    self.create()

    # throw BufReadPost
    self.initDone(self.vimProxyInId)

  def startProc(self, id, cmd):
    try:
      (pid, fd) = os.forkpty()
    except Exception as e:
      log.exception("ProcRunner.startProc: exception while forkpty(): ")
      return False

    sh = '/bin/sh'

    if pid == 0:
      # child
      try: os.execlp(sh, sh, '-c', cmd)
      except Exception as e:
        log.error("ProcRunner.startProc: exception: %s", str(e))
      os._exit(1)
      return False

    # daddy

    # set raw mode
    # several reasons:
    # a) suppress echos
    # b) prevents size limitation while sending data to child processes
    tty.setraw(fd)

    self.processes[id] = fd
    self.invProcesses[fd] = id
    self.main.proxy.addProc(fd)

    log.debug("ProcRunner.startProc %d : %s started", id, cmd)
    return True

  def writeRawToVim(self, data):
    log.debug("Main.writeRawToVim: data: '%s'", data.strip())
    try: self.vimSocket.sendall(data)
    except Exception as e:
      log.exception("Main.writeRawToVim: exception: ")
      return False
    return True

  def writeRawToProc(self, id, data):
    log.debug("ProcRunner.writeRawToProc: data: '%s'", data.strip())
    if data[-1:] != "\\n": data += "\n"

    try:
      desc = self.processes[id]
      os.write(desc, data)
    except Exception as e:
      log.exception("ProcRunner.writeRawToProc: exception: ")
      return False
    return True

  def fromVim(self, data):
    self.process(data)

    data = self.getLastInsert(self.vimProxyOutId)
    log.debug("ProcRunner.fromVim: %s", data)

    if data == None:
      return

    def execCmd(m):
      try:
        id = int(m.group(1))
        cmd = m.group(2)
      except:
        log.exception("ProcRunner.fromVim.execCmd: exception")
        return False
    
      if not self.startProc(id, cmd):
        log.error("ProcRunner.fromVim.execCmd: unable to start command (%s)", cmd)
        return False

      self.sendToVim(self.protoStarted % (id))
      return True

    def killCmd(m):
      log.warning("ProcRunner.fromVim.killCmd: TO IMPLEMENT")
      return False

    def dataCmd(m):
      try:
        id = int(m.group(1))
        data = m.group(2)
      except:
        log.exception("ProcRunner.fromVim.dataCmd: exception")
        return False

      self.writeRawToProc(id, data)
      return True

    def dataAndPauseCmd(m):
      try:
        id = int(m.group(1))
        pauseAfter = int(m.group(2))
        data = m.group(3)
      except:
        log.exception("ProcRunner.fromVim.dataCmd: exception")
        return False

      self.pauseVimMessages(after=pauseAfter, procId=id)

      self.writeRawToProc(id, data)
      return True

    def pauseCmd(m):
      self.pauseVimMessages(after=0)

    def continueCmd(m):
      self.continueVimMessages()

    regexps = [
      (self.reProtoExecCmd, execCmd),
      (self.reProtoKillCmd, killCmd),
      (self.reProtoDataCmd, dataCmd),
      (self.reProtoDataAndPauseCmd, dataAndPauseCmd),
      (self.reProtoPauseCmd, pauseCmd),
      (self.reProtoContinueCmd, continueCmd)
    ]

    for (r, cb) in regexps:
      m = r.match(data)
      if m == None: continue
      cb(m)
      return

    log.error("ProcRunner.fromVim: data out of protocol: '%s'", data)

  def fromProc(self, desc, data):
    id = self.invProcesses[desc]

    log.debug("ProcRunner.fromProc: %d : %s" % (id, data))
    self.sendToVim(self.protoData % (id, data))

    if self.pauseAfter > 0 and self.pauseAfterProcId == id:
      self.pauseAfter -= 1
      if self.pauseAfter == 0:
        self.isPause = True

  def sendToVim(self, data):
    if self.isPause:
      self.pausedMessages.append(data)
      return True

    # NOTE: 
    # when vim receive insert() and initDone(), it set the buffer as visible,
    # this is not what we want. In order to hide this behavior, either
    # a) call getCursor() before and then setDot() which is not efficient and 
    # not always reliable, or 
    # b) autocmd vim's events to keep track of the current buffer and then set the buffer

    # b)
    self.startAtomic()
    self.insert(self.vimProxyInId, 99999, data.strip())
    self.initDone(self.vimProxyInId)
    self.endAtomic()

    # a)
    #def cb(bufId, lnum, column, offset):
    #  self.startAtomic()
    #  self.insert(self.vimProxyInId, 99999, data.strip())
    #  self.initDone(self.vimProxyInId)
    #  if bufId >= 0:
    #    self.setDot(bufId, offset)
    #  self.endAtomic()
    #self.getCursor(cb)

  def send(self, data):
    self.writeRawToVim(data)

  # Events

  def onInsert(self, bufId, offset, text):
    NetBeans.onInsert(self, bufId, offset, text)

    text = text.strip()
    if text in ['', '\\n', '\\t']:
      return

    if not self.buffersInserts.has_key(bufId):
      self.buffersInserts[bufId] = []

    self.buffersInserts[bufId].append(text)

  def onStartupDone(self):
    NetBeans.onStartupDone(self)

    self.setupInOutBuffers()

  def onDisconnect(self):
    NetBeans.onDisconnect(self)

    self.main.proxy.stop()

  def onFileOpened(self, filename, opened, modified):
    NetBeans.onFileOpened(self, filename, opened, modified)

  def onKilled(self, bufId):
    NetBeans.onKilled(self, bufId)

  # Commands and functions callback

  def cmdPutBufferNumber(self, bufId, filename):
    self.netbeansBuffer(bufId, False)
    self.stopDocumentListen(bufId)

  def cmdStopDocumentListen(self, bufId):
    #log.debug("ProcRunner.cmdStopDocumentListen: %d : stopDocumentListen", bufId)
    pass


class Main:

  def __init__(self, daemon, netbeansPort):
    self.daemon           = daemon
    self.netbeansPort     = netbeansPort

    self.netbeans         = None

    self.proxy            = None

  @CatchAndLogException
  def run(self):
    if self.daemon:
      if not self.createDaemon():
        log.error("Main.run: unable to become a daemon")
        return False

    vimSocket = self.startServerAndWaitVim(DEFAULT_NETBEANS_INTERFACE, self.netbeansPort)
    if vimSocket == None:
      log.error("Main.run: unable to startServerAndWaitVim")
      return False

    self.netbeans = ProcRunner(self, vimSocket)

    self.proxy = Proxy(vimSocket, self.netbeans)

    self.proxy.run()

    log.info("Main.run: this is the end my friends")
    return True

  def createDaemon(self):
    try: pid = os.fork()
    except:
      log.exception("Main.createDaemon: unable to become a daemon by forking")
      return False
    
    if pid:
      # parent
      os._exit(1)
      return False

    # child
    os.setsid()
    return True

  def startServerAndWaitVim(self, interface, port):
    try:
      server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      server.bind((interface, port))
      server.listen(1)
    except Exception as e:
      log.exception("Main.startServerAndWaitVim: got exception: ")
      return None

    try:
      log.info("Listening on port %d, waiting for connection", port)
      (con, addr) = server.accept()
    except:
      log.error("Main.startServerAndWaitVim: interrupted while waiting for connection")
      return None

    log.debug("Vim is here! :)")
    return con



def main():
  parser = OptionParser()
  parser.add_option('-l', '--log',
                    dest='log',
                    help='log filename')
  parser.add_option('-p', '--port',
                    dest='port',
                    help='netbeans port number')
  parser.add_option('-g', '--background',
                    dest='background',
                    action="store_true",
                    help='become a daemon')

  (options, args) = parser.parse_args()

  logfile = DEFAULT_LOG_FILENAME
  if options.log != None:
    logfile = options.log

  LogSetup().setup('', logfile)

  port = DEFAULT_NETBEANS_PORT
  if options.port != None:
    try: port = int(options.port)
    except:
      log.error("Invalid port number ("+options.port+")")
      return 1

  daemon = False
  if options.background:
    daemon = True

  log.debug("Starting")

  main = Main(daemon, port)
  if not main.run():
    log.error("Ended with errors, see logs for details")
    return 1

  return 0


if __name__ == '__main__':
  ret = main()
  sys.exit(ret)

