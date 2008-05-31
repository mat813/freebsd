#!/usr/bin/env python

# $FreeBSD$

import sys, locale
from svn import repos, fs
locale.setlocale(locale.LC_ALL, 'C')

def canonicalize(path):
  return path.decode('utf-8').lower().encode('utf-8')

def get_new_paths(txn_root):
  new_paths = []
  for path, change in fs.paths_changed(txn_root).iteritems():
    if (change.change_kind == fs.path_change_add
        or change.change_kind == fs.path_change_replace):
      new_paths.append(path)
  return new_paths

def split_path(path):
  slash = path.rindex('/')
  if (slash == 0):
    return '/', path[1:]
  return path[:slash], path[slash+1:]

def join_path(dir, name):
  if (dir == '/'):
    return '/' + name
  return dir + '/' + name

def ensure_names(path, names, txn_root):
  if (not names.has_key(path)):
     names[path] = []
     for name, dirent in fs.dir_entries(txn_root, path).iteritems():
       names[path].append([canonicalize(name), name])

names = {}   # map of: key - path, value - list of two element lists of names
clashes = {} # map of: key - path, value - map of: key - path, value - dummy

native = locale.getlocale()[1]
if not native: native = 'ascii'
repos_handle = repos.open(sys.argv[1].decode(native).encode('utf-8'))
fs_handle = repos.fs(repos_handle)
txn_handle = fs.open_txn(fs_handle, sys.argv[2].decode(native).encode('utf-8'))
txn_root = fs.txn_root(txn_handle)

new_paths = get_new_paths(txn_root)
for path in new_paths:
  dir, name = split_path(path)
  canonical = canonicalize(name)
  ensure_names(dir, names, txn_root)
  for name_pair in names[dir]:
    if (name_pair[0] == canonical and name_pair[1] != name):
      canonical_path = join_path(dir, canonical)
      if (not clashes.has_key(canonical_path)):
        clashes[canonical_path] = {}
      clashes[canonical_path][join_path(dir, name)] = True
      clashes[canonical_path][join_path(dir, name_pair[1])] = True


 def do_cat(self, arg):
    """dump the contents of a file"""
    if not len(arg):
      print "You must supply a file path."
      return
    catpath = self._parse_path(arg)
    kind = fs.check_path(self.root, catpath)
    if kind == core.svn_node_none:
      print "Path '%s' does not exist." % catpath
      return
    if kind == core.svn_node_dir:
      print "Path '%s' is not a file." % catpath
      return
    ### be nice to get some paging in here.
    stream = fs.file_contents(self.root, catpath)
    while 1:
      data = core.svn_stream_read(stream, core.SVN_STREAM_CHUNK_SIZE)
      sys.stdout.write(data)
      if len(data) < core.SVN_STREAM_CHUNK_SIZE:
        break

