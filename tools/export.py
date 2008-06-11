#!/usr/local/bin/python

# $FreeBSD$

import string
import sys
import time
import os
import popen2
import tempfile
from svn import core, fs, delta, repos


# SVN's API structure is to do callbacks to a class to get notifications
class ChangeReceiver(delta.Editor):
  def __init__(self, fs_root, base_root, rev, fs_ptr, pool):
    self.fs_root = fs_root
    self.base_root = base_root
    self.fs_ptr = fs_ptr
    self.rev = int(rev)
    self.pool = pool
    self.changes = []

  def delete_entry(self, path, revision, parent_baton, pool):
    ### need more logic to detect 'replace'
    if fs.is_dir(self.base_root, '/' + path):
      pass
    else:
      self.changes.append(['D', path])

  def add_file(self, path, parent_baton,
               copyfrom_path, copyfrom_revision, file_pool):
    self.changes.append(['A', path])
    return [ '_', ' ', None ]

  def open_file(self, path, parent_baton, base_revision, file_pool):
    return [ '_', ' ', path ]

  def apply_textdelta(self, file_baton, base_checksum):
    text_mod, prop_mod, path = file_baton
    file_baton[0] = 'U'
    # no handler
    return None

  def change_file_prop(self, file_baton, name, value, pool):
    text_mod, prop_mod, path = file_baton
    file_baton[1] = 'U'

  def close_file(self, file_baton, text_checksum):
    text_mod, prop_mod, path = file_baton
    # test the path. it will be None if we added this file.
    if path:
      status = text_mod + prop_mod
      # was there some kind of change?
      if status != '_ ':
        self.changes.append(['U', path])

# Last path component
def _basename(path):
  idx = path.rfind('/')
  if idx == -1:
    return path   
  return path[idx+1:]

# Directory component
def _dirname(path):
  idx = path.rfind('/')
  if idx == -1:
    return ''
  return path[:idx]

# Keep track of best common prefix per directory group to keep commit time down
class pathcollector():
  def __init__(self):
    self.paths = {}

  # Not really a set..  calculates common prefix instead.
  def __setitem__(self, prefix, dir):
    # If we haven't seen a dir, start here
    if not self.paths.has_key(prefix):
      self.paths[prefix] = dir
      return
    # If it is the same dir, we're finished
    if self.paths[prefix] == dir:
      return
    # See if we've found a common parent
    parent = dir
    while _dirname(parent) != parent:
      parent = _dirname(parent)
      # See if common prefix works
      if self.paths[prefix] == parent:
	return
      # Raise common prefix
      if self.paths[prefix].startswith(parent):
	self.paths[prefix] = parent
	return
    print "WTF?"
    assert false

  def __iter__(self):
    return self.paths.iteritems()

# Issue a cvs command, aborting if a problem happens
def do_cvs(cvspath, dir, cmd):
  ioerror = False
  print("cvs path %s, dir %s, cmd %s" % (cvspath, dir, cmd))
  cwd = os.getcwd()
  os.chdir(os.path.join(cvspath, dir))
  pipe = popen2.Popen3(cmd)
  os.chdir(cwd)
  output = ''
  try:
    output = pipe.fromchild.readlines()
    pipe.fromchild.close()
    pipe.tochild.close()
  except IOError:
    ioerror = True
  rv = pipe.wait()
  failed = (rv != 0) or ioerror
  print 'Cvs output: ', output
  return failed

# Dump a file from svn into cvs.  This has to apply the delta to the previous rev.
def dump_file(fs_ptr, fs_root, rev, svnpath, cvspath, author, date, pool, workpath):
  kw = fs.node_prop(fs_root, svnpath, core.SVN_PROP_KEYWORDS)
  if not kw:
    kw = ''
  str = '$' + 'FreeBSD: %s %s %s %s $' % (cvspath, rev, date, author)
  #str = '$' + 'FreeBSDId: %s %s %s %s $' % (cvspath, rev, date, author)
    
  print 'Author: ' + author
  subpool = core.svn_pool_create(pool)
  stream = core.Stream(fs.file_contents(fs_root, svnpath, subpool))
  string = ""
  while 1:
    data = stream.read(core.SVN_STREAM_CHUNK_SIZE)
    string += data
    if len(data) < core.SVN_STREAM_CHUNK_SIZE:
      break
  # Expand keywords
#  if kw == r'FreeBSD=%H':
#    old = '$' + 'FreeBSD$'
#    string = string.replace(old, str)
  cvsfile = os.path.join(workpath, cvspath)
#  sys.stdout.write('File contents:\n=========\n')
#  sys.stdout.write(string)
#  sys.stdout.write('=========\n')
  executable = fs.node_prop(fs_root, svnpath, core.SVN_PROP_EXECUTABLE)
  if executable:
    mode = 0777
  else:
    mode = 0666
  outfile = os.open(cvsfile, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, mode)
  if not outfile:
    sys.exit('cannot open %s for write' % cvsfile)
  n = os.write(outfile, string)
  if n != len(string):
    sys.exit('short write. %d instead of %d' % (n, len(string)))
  os.close(outfile)
  core.svn_pool_destroy(subpool)

# List of paths we export to cvs, and what branch tag (or None for HEAD)
# Hard coded for now.  This will be automatically implied based on path transforms.
maptable = [
  # -current head
  ( 'head/',        None ),
  # -stable branches
  ( 'stable/2.0.5/', 'RELENG_2_0_5' ),
  ( 'stable/2.1/',   'RELENG_2_1_0' ),
  ( 'stable/2.2/',   'RELENG_2_2' ),
  ( 'stable/3/',     'RELENG_3' ),
  ( 'stable/4/',     'RELENG_4' ),
  ( 'stable/5/',     'RELENG_5' ),
  ( 'stable/6/',     'RELENG_6' ),
  ( 'stable/7/',     'RELENG_7' ),
  # errata / security / releng branches
  ( 'releng/ALPHA_2_0/','ALPHA_2_0' ),
  ( 'releng/BETA_2_0/', 'BETA_2_0' ),
  ( 'releng/4.3/',   'RELENG_4_3' ),
  ( 'releng/4.4/',   'RELENG_4_4' ),
  ( 'releng/4.5/',   'RELENG_4_5' ),
  ( 'releng/4.6/',   'RELENG_4_6' ),
  ( 'releng/4.7/',   'RELENG_4_7' ),
  ( 'releng/4.8/',   'RELENG_4_8' ),
  ( 'releng/4.9/',   'RELENG_4_9' ),
  ( 'releng/4.10/',  'RELENG_4_10' ),
  ( 'releng/4.11/',  'RELENG_4_11' ),
  ( 'releng/4.12/',  'RELENG_4_12' ),
  ( 'releng/5.0/',   'RELENG_5_0' ),
  ( 'releng/5.1/',   'RELENG_5_1' ),
  ( 'releng/5.2/',   'RELENG_5_2' ),
  ( 'releng/5.3/',   'RELENG_5_3' ),
  ( 'releng/5.4/',   'RELENG_5_4' ),
  ( 'releng/5.5/',   'RELENG_5_5' ),
  ( 'releng/5.6/',   'RELENG_5_6' ),
  ( 'releng/6.0/',   'RELENG_6_0' ),
  ( 'releng/6.1/',   'RELENG_6_1' ),
  ( 'releng/6.2/',   'RELENG_6_2' ),
  ( 'releng/6.3/',   'RELENG_6_3' ),
  ( 'releng/6.4/',   'RELENG_6_4' ),
  ( 'releng/7.0/',   'RELENG_7_0' ),
  ( 'releng/7.1/',   'RELENG_7_1' ),
  ( 'releng/7.2/',   'RELENG_7_2' ),
]

def map2cvs(svnpath):
  for prefix, branch in maptable:
    plen = len(prefix)
    if svnpath.startswith(prefix):
      return 'src/' + svnpath[plen:], branch
  return None, None

# Add intermediate directories to the cvs checkout area as needed.
# XXX should use 'cvs update -d -l' if the dir exists in cvsroot
def makedirs(cvspath, path):
  #print 'Makedirs:', cvspath, path
  if not path.startswith('src'):
    sys.exit('Illegal path %s' % path)
  if path == 'src':
    return
  makedirs(cvspath, _dirname(path))
  fullpath = os.path.join(cvspath, path)
  if os.path.isfile(fullpath):
     sys.exit('Dest dir is a file' % path)
  if not os.path.isdir(fullpath):
    try:
      #print "Making directory " + fullpath
      os.makedirs(fullpath)
      failed = do_cvs(cvspath, _dirname(path), "cvs -q add %s" % _basename(path))
      assert not failed
    except OSError:
      sys.exit('Cannot mkdir %s' % path)
  #print 'Dirpath complete: ' + path

# Export a single change to cvs.
def exportrev(pool, fs_ptr, rev, cvspath):
  def authz_cb(root, path, pool):
    return True

  subpool = core.svn_pool_create(pool)
  # Connect up to the revision
  fs_root = fs.revision_root(fs_ptr, rev, subpool)
  base_root = fs.revision_root(fs_ptr, rev - 1, subpool)
  editor = ChangeReceiver(fs_root, base_root, rev, fs_ptr, subpool)
  e_ptr, e_baton = delta.make_editor(editor, subpool)
  repos.dir_delta(base_root, '', '', fs_root, '', e_ptr, e_baton, authz_cb, 0, 1, 0, 0, subpool)

  # Author
  author = fs.revision_prop(fs_ptr, rev, core.SVN_PROP_REVISION_AUTHOR)
  if not author:
    author = 'NoAuthor'
  if author == 'davidg':
    author = 'dg'
  os.environ['CVS_AUTHOR'] = author

  # Date
  date = fs.revision_prop(fs_ptr, rev, core.SVN_PROP_REVISION_DATE)
  if date:
    aprtime = core.svn_time_from_cstring(date)
    secs = aprtime / 1000000  # aprtime is microseconds; make seconds
    tm = time.gmtime(secs)
    date = time.strftime('%Y-%m-%d %H:%M:%SZ', tm)
    os.environ['CVS_TIMESTAMP'] = "%d" % secs
  else:
    date = 'NoDate'
    if os.environ.has_key('CVS_TIMESTAMP'):
      del os.environ['CVS_TIMESTAMP']

  # Build log message to export
  cvslog = 'SVN rev %d on %s by %s\n' % (rev, date, author)
  svnlog = fs.revision_prop(fs_ptr, rev, core.SVN_PROP_REVISION_LOG)
  if svnlog:
    cvslog += '\n' + svnlog

  pc = pathcollector()

  for k, p in editor.changes:
    #print 'Path ', p
    if p == 'svnadmin/conf/access':
      path = 'CVSROOT'
      workpath = 'CVSROOT/access'
      dump_file(fs_ptr, fs_root, rev, p, path, author, date, subpool, workpath)
      pc[workpath] = 'CVSROOT'
      continue
    (path, tag) = map2cvs(p)
    if not path:
      continue
    if tag:
      workpath = os.path.join(cvspath, tag)
      uptag = '-r ' + tag
    else:
      workpath = cvspath
      uptag = '-A'
    #print workpath
    if not os.path.isdir(workpath):
      os.makedirs(workpath)
    if not os.path.isdir(os.path.join(workpath, 'src')):
      failed = do_cvs(workpath, '', "cvs -Rq co %s src" % uptag)
      assert not failed
    # at this point, the top directory and /src should exist
    #print p, path, k
    makedirs(workpath, _dirname(path))
    # Now the directory for the files must exist, and branch tag will be sticky
    assert os.path.isdir(os.path.join(workpath, _dirname(path)))
    assert k == 'A' or k == 'U' or k == 'D'

    if k == 'A' or k == 'U':
      print 'add/update file ' + path + '.'
      destpath = os.path.join(workpath, path)
      existed = os.path.isfile(destpath)
      dump_file(fs_ptr, fs_root, rev, p, path, author, date, subpool, workpath)
      if not existed:
	print 'cvs add file ' + path + '.'
	failed = do_cvs(workpath, _dirname(path), "cvs -q add %s" % _basename(path))
	assert not failed
    elif k == 'D':
      print 'cvs rm -f file ' + path + '.'
      failed = do_cvs(workpath, _dirname(path), "cvs -q rm -f %s" % _basename(path))
      assert not failed
    pc[workpath] = _dirname(path)

  # aggregate the commit
  for root, dir in pc:
    fd, logfile = tempfile.mkstemp()
    os.write(fd, cvslog)
    os.close(fd)
    failed = do_cvs(root, dir, "cvs -q commit -F %s" % logfile)
    assert not failed
    os.remove(logfile)
  core.svn_pool_destroy(subpool)

# Loop for the export range
def export(pool, repos_path, cvspath):
  repos_path = core.svn_path_canonicalize(repos_path)
  fs_ptr = repos.fs(repos.open(repos_path, pool))
  os.environ['CVSROOT'] = '/r/ncvs'
  while True:
    if not os.path.isfile('/tmp/do_export.txt'):
      sys.exit('/tmp/do_export.txt does not exist')
    curr_rev = fs.youngest_rev(fs_ptr)
    last_rev = int(fs.revision_prop(fs_ptr, 0, 'fbsd:lastexp'))
    if last_rev < curr_rev:
      print '%d %s' % (last_rev, curr_rev)
      rev = '%d' % (last_rev + 1)
      print '==========> export rev ' + rev
      exportrev(pool, fs_ptr, last_rev + 1, cvspath)
      fs.change_rev_prop(fs_ptr, 0, 'fbsd:lastexp', rev)
      continue
    print "."
    time.sleep(15)


if __name__ == '__main__':
  core.run_app(export, '/r/svnmirror/base', '/r/svn2cvs/cvs')
