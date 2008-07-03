#!/usr/local/bin/python

# $FreeBSD$
# Loosely based on verify-po.py from tools/hook-scripts

import string
import sys
import re
import os.path
from svn import core, fs, delta, repos

# POLICY: if cvs2svn:cvs-rev must not be set.
# POLICY: mime-type must be unset, text/*, application/* or image/*
# POLICY: if a file does has fbsd:nokeywords, then svn:keywords must not be set
# POLICY: if a file has binary chars and no fbsd:notbinary, then pretend its not binary
# POLICY: if a file is binary, then it must have mime application/* or image/*
# POLICY: if a file does not have fbsd:nokeywords, or is binary then svn:keywords must be set
# POLICY: if svn:keywords is set, $ FreeBSD $ must be present and condensed.
# POLICY: If a file has text/*, then it must have eol-style


text_characters = "".join(map(chr, range(32, 127)) + list("\n\r\t\b"))
_null_trans = string.maketrans("", "")
okkw = '$' + 'FreeBSD' + '$'
badkw = '\$' + 'FreeBSD' + ':.*\$'

def is_binary(s):
    if not s:      # Empty files are considered text
        return False
    if "\0" in s:  # NUL char == instant binary classification
        return True

    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    t = s.translate(_null_trans, text_characters)

    # If more than 30% non-text characters, then
    # this is considered a binary file
    # XXX if we include > 128, then reduce fraction
    if len(t) > len(s) * 0.30:
        return True

    # No reason to call it binary
    return False

def mime_ok(mime):
  "Return True if we accept the mime type"
  if mime == 'unspecified':
    return True
  if mime.startswith('text/'):
    return True
  if mime.startswith('application/'):
    return True
  if mime.startswith('image/'):
    return True
  return False

def check_keywords(s, exempt):
  "Check if the keyword is ok"
  r = re.compile(badkw)
  if r.search(s):
    return False
  if exempt:
    return True
  if s.find(okkw) != -1:
    return True
  return False

# List of directories that we do keyword checking in
kw_dirs = [
  r'svnadmin/',
  r'head/',
  r'stable/',
  r'releng/',
  r'release/',
]

# How much of path to strip off to get canonical pathname
kw_prefixes = [
  r'head/',
  r'releng/[^/]+/',
  r'release/[^/]+/',
  r'stable/[^/]+/',
]

kw_exclude = []

def kw_checks_exempt(path):
  # Check to see if we're in a directory that has keyword checking enabled
  for prefix in kw_dirs:
    if path.startswith(prefix):
      break
  else:
    return True
  # First, strip off stable/7/, releng/7.0/ etc to get canonical paths
  for prefix in kw_prefixes:
    r = re.compile(prefix)
    if r.match(path):
      path = r.sub('', path, 1)
  # Now, with a canonical path, check for exclusions.
  for prefix in kw_exclude:
    r = re.compile(prefix)
    if r.match(path):
      return True
  return False

class ChangeReceiver(delta.Editor):
  def __init__(self, txn_root, base_root, pool):
    self.txn_root = txn_root
    self.base_root = base_root
    self.pool = pool
    self.failed = 0

  def do_fail(self, msg):
    if self.failed == 1:
      sys.stderr.write("== Additional errors may compound and may not be accurate ==\n")
    self.failed += 1
    sys.stderr.write(msg)

  def did_fail(self):
    return self.failed

  def add_file(self, path, parent_baton,
               copyfrom_path, copyfrom_revision, file_pool):
    return [0, path]

  def open_file(self, path, parent_baton, base_revision, file_pool):
    return [0, path]

  def apply_textdelta(self, file_baton, base_checksum):
    file_baton[0] = 1
    # no handler
    return None

  def close_file(self, file_baton, text_checksum):
    changed, path = file_baton
    if not changed:
      return

    # POLICY: if cvs2svn:cvs-rev must not be set. period.
    cvsrev = fs.node_prop(self.txn_root, path, 'cvs2svn:cvs-rev')
    if cvsrev:
      self.do_fail('Path "%s" needs to have "cvs2svn:cvs-rev" removed with "svn propdel".\n' % path)

    # POLICY: mime-type must be unset, text/*, application/* or image/*
    mimetype = fs.node_prop(self.txn_root, path, core.SVN_PROP_MIME_TYPE)
    if not mimetype:
      mimetype = 'unspecified'
    if not mime_ok(mimetype):
      self.do_fail('Path "%s" has an unknown mime type "%s"\n' % (path, mimetype))

    # POLICY: if a file does has fbsd:nokeywords, then svn:keywords must not be set
    fbsd_nokeywords = fs.node_prop(self.txn_root, path, 'fbsd:nokeywords')
    keywords = fs.node_prop(self.txn_root, path, core.SVN_PROP_KEYWORDS)
    if fbsd_nokeywords and keywords:
      self.do_fail('Path "%s" has fbsd:nokeywords AND svn:keywords. Remove one.\n' % path)

    subpool = core.svn_pool_create(self.pool)
    stream = core.Stream(fs.file_contents(self.txn_root, path, subpool))
    str_list = []
    while 1:
      data = stream.read(core.SVN_STREAM_CHUNK_SIZE)
      str_list.append(data)
      if len(data) < core.SVN_STREAM_CHUNK_SIZE:
	break
    string = ''.join(str_list)

    # XXX: check for charset in mime type; bypass binary test if charset is present.
    # POLICY: if a file has binary chars and fbsd:notbinary, then pretend its not binary
    binary = is_binary(string)
    fbsd_notbinary = fs.node_prop(self.txn_root, path, 'fbsd:notbinary')
    if binary and fbsd_notbinary:
      binary = False

    # POLICY: if a file is binary, then it must have mime application/* or image/*
    if binary:
      if not mimetype.startswith('application/') and not mimetype.startswith('image/'):
	self.do_fail('Path "%s" contains binary but has svn:mime-type "%s"\n' % (path, mimetype))
	sys.stderr.write('Try application/* (application/octet-stream) or image/* instead.\n')

    # See which paths don't require the svn:keywords property, or don't need the $ FreeBSD $ string.
    kw_exempt = kw_checks_exempt(path)

    # POLICY: if a file does not have fbsd:nokeywords, and is not binary then svn:keywords must be set
    if binary:
      fbsd_nokeywords = True
    if not fbsd_nokeywords and not kw_exempt:
      kw = r'FreeBSD=%H'
      if not keywords:
	self.do_fail('Path "%s" is missing the svn:keywords property (or an fbsd:nokeywords override)\n' % path)
      elif keywords != kw:
	self.do_fail('Path "%s" should have svn:keywords set to %s\n' % (path, kw))

    # POLICY: if svn:keywords is set, $ FreeBSD $ must be present and condensed.
    if keywords and not check_keywords(string, kw_exempt):
      self.do_fail('Path "%s" does not have a valid %s string (keywords not disabled here)\n' % (path, okkw))

    # POLICY: If a file has text/*, then it must have eol-style
    eolstyle = fs.node_prop(self.txn_root, path, core.SVN_PROP_EOL_STYLE)
    if mimetype.startswith('text/') and not eolstyle:
      self.do_fail('Path "%s" is text but is missing svn:eol-style property\n' % path)

    # Whew!
    core.svn_pool_destroy(subpool)


def verify(pool, repos_path, mode, rev_or_txn):
  def authz_cb(root, path, pool):
    return True

  for line in open(os.path.join(repos_path, 'conf', 'exclude')):
    ln = line.strip()
    if not ln.startswith('#') and ln != '':
      kw_exclude.append(ln)
  fs_ptr = repos.fs(repos.open(repos_path, pool))
  if mode == '-r':
    rev = int(rev_or_txn)
    txn_root = fs.revision_root(fs_ptr, rev)
    txn_base = rev - 1
  elif mode == '-t':
    txn_ptr = fs.open_txn(fs_ptr, rev_or_txn, pool)
    txn_root = fs.txn_root(txn_ptr, pool)
    txn_base = fs.txn_base_revision(txn_ptr)
  else:
    sys.exit("arg 2 must be -r or -t")
  base_root = fs.revision_root(fs_ptr, txn_base, pool)
  editor = ChangeReceiver(txn_root, base_root, pool)
  e_ptr, e_baton = delta.make_editor(editor, pool)
  repos.dir_delta(base_root, '', '', txn_root, '', e_ptr, e_baton, authz_cb, 0, 1, 0, 0, pool)
  fails = editor.did_fail()
  if fails > 0:
    if mode == '-r':
      sys.stderr.write('== Rev %d problem count: %d\n' % (rev, fails))
    else:
      sys.stderr.write('== Pre-commit problem count: %d\n' % fails)
    sys.exit(1)

if __name__ == '__main__':
  assert len(sys.argv) == 4
  core.run_app(verify, sys.argv[1], sys.argv[2], sys.argv[3])
