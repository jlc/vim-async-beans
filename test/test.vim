" test.vim
"

let cmd = '/Users/jeanluc/.vim/addons/vim-async-beans/test/TestPingProc.py'
"let cmd = "cd /Users/jeanluc/.vim/addons/ensime/dist_2.9.2-RC1 && ./bin/server '/tmp/portfile'"
let s:ctx = {'cmd':cmd, 'move_last':1, 'line_prefix': 'server  : '}

let s:ctx2 = {'cmd':cmd, 'move_last':1, 'line_prefix': 'bis : '}

let s:counter = 3

fun! s:ctx.receive(data)
  Decho("ctx.receive: ".a:data)
endfun

fun! s:ctx2.receive(data)
  Decho("ctx2.receive: ".a:data)
endfun

fun! s:ctx.started()
  Decho("started")
endfun

fun! s:ctx2.started()
  Decho("started 2")
endfun

fun! s:ctx.terminated()
  Decho("terminated")
endfun

fun! s:ctx2.terminated()
  Decho("terminated 2")
endfun

fun! test#start()
  call abeans#exec(s:ctx)
  "call abeans#exec(s:ctx2)
  "call async_porcelaine#LogToBuffer(s:ctx)
endfun

fun! test#write()
  call s:ctx.write("Hello World!")
endfun

fun! test#write2()
  call s:ctx2.write("SECOND ! Hello World!")
endfun
