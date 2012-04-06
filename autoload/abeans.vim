" autoload/abeans.vim
"
" Copyright 2012 Jeanluc Chasseriau <jeanluc@lo.cx>
" 
" Licensed under the Apache License, Version 2.0 (the "License");
" you may not use this file except in compliance with the License.
" You may obtain a copy of the License at
" 
" http://www.apache.org/licenses/LICENSE-2.0
" 
" Unless required by applicable law or agreed to in writing, software
" distributed under the License is distributed on an "AS IS" BASIS,
" WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
" See the License for the specific language governing permissions and
" limitations under the License.

if !exists('g:abeans')
  let g:abeans = {}
endif

let g:abeans['addon-dir'] = get(g:abeans, 'addon-dir', expand('<sfile>:h:h'))
let g:abeans['ctxs'] = get(g:abeans, 'ctxs', {})
let g:abeans['connected'] = get(g:abeans, 'connected', 0)

python << endpython
import vim
import sys
import os
import re
import logging
sys.path.append(vim.eval("g:abeans['addon-dir']") + '/python')
from LogBeans import *

VIM_BUFFER_OUT_ID = 0
VIM_BUFFER_OUT_FILENAME = 'vim-async-beans.out'
VIM_BUFFER_IN_ID = 0
VIM_BUFFER_IN_FILENAME = 'vim-async-beans.in'

EXEC_CMD        = "##_EXEC_%d_[%s]_##"
KILL_CMD        = "##_KILL_%d_##"

RE_STARTED      = re.compile("^##_STARTED_(\d+)_##$")
RE_TERMINATED   = re.compile("^##_TERMINATED_(\d+)_##$")
RE_DATA         = re.compile("^##_DATA_(\d+)_##(.*)$")

NEXT_CTX_ID = 1

initLog('abeans', 'abeans.vim.log')

# When using a 'log' variable, we may refer to another one defined somewhere else
def ablog(): return logging.getLogger('abeans')

def getNextId():
  global NEXT_CTX_ID
  id = NEXT_CTX_ID
  NEXT_CTX_ID += 1
  return id

def onStarted(m):
  try: id = int(m.group(1))
  except Exception as e:
    ablog().exception("onStarted: match group exception")

  vim.command("let g:abeans.ctxs[%d].running = 1" % (id))
  vim.command("call g:abeans.ctxs[%d].started()" % (id))

def onTerminated(m):
  try: id = int(m.group(1))
  except Exception as e:
    ablog().exception("onTerminated: match group exception")

  vim.command("let g:abeans.ctxs[%d].running = 0" % (id))
  vim.command("call g:abeans.ctxs[%d].terminated()" % (id))

def onData(m):
  try:
    id = int(m.group(1))
    data = m.group(2)
  except Exception as e:
    ablog().exception("onData: match group exception")
 
  ablog().debug("onData: %d : %s", id, data)

  data = data.replace('"', '\\\"') + "\n"
  vim.command("let on_data_result_%d = \"%s\"" % (id, data))
  vim.command("call g:abeans.ctxs[%d].receive(on_data_result_%d)" % (id, id))

def parse(line):
  global RE_STARTED, RE_TERMINATED, RE_DATA
  regexps = [
    (RE_STARTED, onStarted),
    (RE_TERMINATED, onTerminated),
    (RE_DATA, onData)
  ]

  for (r, cb) in regexps:
    m = r.match(line)
    if m == None: continue
    cb(m)
    return

  ablog().error("parse: unmatched line: '%s'" % (line))

# updateBuffer()
# update given buffer by executing given function
# take care of setting buffer options
def updateBuffer(id, f):
  preCmds = [
    "buffer %d" % (id),
    "setlocal modifiable",
  ]
  postCmds = [
    "setlocal nomodifiable",
    "buffer %d" % (vim.current.buffer.number)
  ]
  vim.command("\n".join(preCmds))
  f()
  vim.command("\n".join(postCmds))

@CatchAndLogException
def send(data):
  doSend = lambda: vim.buffers[VIM_BUFFER_OUT_ID - 1].append(data)
  updateBuffer(VIM_BUFFER_OUT_ID, doSend)

@CatchAndLogException
def startExec(cmd):
  global EXEC_CMD
  id = getNextId()
  start = EXEC_CMD % (id, cmd)
  send(start)
  return id

@CatchAndLogException
def processInput():
  global VIM_BUFFER_IN_ID
  id = VIM_BUFFER_IN_ID - 1 # array index start at 0
  lines = []
  lines.extend(vim.buffers[id])

  def clear():
    for i in range(len(vim.buffers[id])):
      del vim.buffers[id][i]

  updateBuffer(VIM_BUFFER_IN_ID, clear)

  for line in lines:
    ablog().debug("processInput: parsing: '%s'", line)
    parse(line)

@CatchAndLogException
def findBuffers():
  global _processInput, VIM_BUFFER_OUT_ID, VIM_BUFFER_IN_ID
  _processInput = processInput
  for buffer in vim.buffers:
    if buffer.name == None: continue
    if os.path.basename(buffer.name) == VIM_BUFFER_OUT_FILENAME:
      VIM_BUFFER_OUT_ID = buffer.number
    if os.path.basename(buffer.name) == VIM_BUFFER_IN_FILENAME:
      VIM_BUFFER_IN_ID = buffer.number

  setBufferOptions(VIM_BUFFER_OUT_ID)
  setBufferOptions(VIM_BUFFER_IN_ID)

  vim.command("buffer %s" % (vim.eval("bufnr('$')")))

_processInput = findBuffers

def setBufferOptions(id):
  options = [
    "buftype=nofile",
    "bufhidden=hide",
    "noswapfile",
    "nobuflisted",
    "nomodifiable"
  ]
  vim.command("buffer %d" % (id))
  vim.command("setlocal "+' '.join(options))
endpython

fun! abeans#start()
  let beansCooker = g:abeans['addon-dir'] . '/python/VimProcRunner.py -g'
  py os.system(vim.eval("beansCooker"))
  sleep 1
  nbstart:127.0.0.1:60101
  if has("netbeans_enabled")
    let g:abeans['connected'] = 1
  else
    let g:abeans['connected'] = 0
    echoe "Error: vim is not connected to VimProcRunner.py, checkout log files for details."
    finish
  endif
endfun

fun! abeans#exec(ctx)
  if !has_key(a:ctx, 'started')
    fun! ctx.started()
    endfun
  endif

  if !has_key(a:ctx, 'terminated')
    fun! ctx.terminated()
    endfun
  endif

  fun! a:ctx.write(data)
    call abeans#write(self, a:data)
  endfun

python << endpython
global EXEC_CMD
cmd = vim.eval("a:ctx.cmd")
id = getNextId()
start = EXEC_CMD % (id, cmd)
send(start)
vim.command("let a:ctx.pid = %d" % (id))
vim.command("let a:ctx.abeans_id = %d" % (id))
vim.command("let g:abeans.ctxs[%d] = a:ctx" % (id))
endpython

endfun

fun! abeans#write(ctx, data)
  py send("##_DATA_%s_##%s" % (vim.eval("a:ctx.abeans_id"), vim.eval("a:data")))
endfun

fun! abeans#kill(ctx)
endfun

fun! abeans#processInput()
  py _processInput()
endfun

