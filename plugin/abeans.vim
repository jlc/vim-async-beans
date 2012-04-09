" plugin/abeans.vim
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

if !exists('g:abeans') | let g:abeans = {} | endif

command! -nargs=0 AsyncBeans call abeans#start()

" noremap <leader>ef :EnvimTypecheckFile<cr>

augroup ASYNCBEANS
  au!

  " setCurrentBuffer: keep tracking where we are
  " DEBUG: pass event name for debugging only
  " BufEnter is catched when entering into vim-async-beans.*
  " If necessary, we should find a way to exclude those ones
  autocmd BufNewFile * :call abeans#setCurrentBuffer("BufNewFile")
  autocmd BufAdd * :call abeans#setCurrentBuffer("BufAdd")
  autocmd BufCreate * :call abeans#setCurrentBuffer("BufCreate")
  autocmd BufFilePost * :call abeans#setCurrentBuffer("BufFilePost")
  autocmd BufNew * :call abeans#setCurrentBuffer("BufNew")
  autocmd TabEnter * :call abeans#setCurrentBuffer("TabEnter")
  autocmd CursorMoved,CursorMovedI * :call abeans#setCurrentBuffer("CursorMoved")

  autocmd BufReadPost vim-async-beans.in :call abeans#processInput()
augroup end
