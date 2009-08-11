#!/usr/local/bin/python

# $FreeBSD$

import string
import sys
import time
import os
import popen2
import tempfile
from svn import core, fs, delta, repos

# Issue an export command, aborting if a problem happens
def do_export(cmd):
  ioerror = False
  pipe = popen2.Popen3(cmd)
  output = ''
  try:
    output = pipe.fromchild.readlines()
    pipe.fromchild.close()
    pipe.tochild.close()
  except IOError:
    ioerror = True
  rv = pipe.wait()
  failed = (rv != 0) or ioerror
  print 'export2 output: ', output
  return failed

# Dump a file from svn into cvs.  This has to apply the delta to the previous rev.
# Loop for the export range
def export(pool, repos_path, cvspath, cvsroot):
  repos_path = core.svn_path_canonicalize(repos_path)
  fs_ptr = repos.fs(repos.open(repos_path, pool))
  while True:
    curr_rev = fs.youngest_rev(fs_ptr)
    last_rev = int(fs.revision_prop(fs_ptr, 0, 'fbsd:lastexp'))
    if last_rev < curr_rev:
      print '%d %s' % (last_rev, curr_rev)
      rev = '%d' % (last_rev + 1)
      print '==========> export rev ' + rev
      cmd = './export2.py %s %s %d %s' % (repos_path, cvspath, last_rev + 1, cvsroot)
      failed = do_export(cmd)
      assert not failed
      fs.change_rev_prop(fs_ptr, 0, 'fbsd:lastexp', rev)
      continue
    print "."
    time.sleep(15)


if __name__ == '__main__':
  print "Version: $FreeBSD$"
  core.run_app(export, '/r/svnmirror/base', '/r/svn2cvs/cvs', '/r/ncvs')
