#!/usr/local/bin/python

# $FreeBSD$

# very vaguely derived from:
# http://www.davidgrant.ca/limit_size_of_subversion_commits_with_this_hook

import sys,os
from svn import core, fs, repos

# This is a safety feature, not a policy restriction.  The svn fsfs repository
# is the sum of all the transaction files.  If you're here, presumably it means
# you were about to add a large transaction.

# Check your 'svn status' output, think carefully and take extra care.  You may
# temporarily add yourself here once you're in the 'careful' frame of mind. :)

# Be sure to remove yourself after you're finished, or you might find yourself
# having to explain a large accident...

def checksize(pool, repo, txn, sizelimit):
  fs_ptr = repos.fs(repos.open(repo, pool))
  txn_ptr = fs.open_txn(fs_ptr, txn, pool)
  user = fs.txn_prop(txn_ptr, "svn:author", pool)
  txnRevPath = repo+'/db/txn-protorevs'+'/'+txn+'.rev'
  size = os.stat(txnRevPath)[6]
  if size < sizelimit:
    return
  try:
    fp = open(repo+"/conf/sizelimit.conf")
    for line in fp:
      line = line.strip()
      if line.startswith('#'):
	continue;
      words = line.split()
      if len(words) == 0:
	continue
      name = words[0]
      if name != user:
	continue
      if len(words) >= 2:
	sizelimit = int(words[1])
      else:
	sizelimit = 10 * 1024 * 1024
      if size < sizelimit:
	return
  except Exception, e:
    sys.stderr.write('sizelimit reading/parsing sizelimit.conf: %s\n' % e)
  sys.stderr.write("Sorry, you are trying to commit a %d byte transaction!\n" % size)
  sys.stderr.write("The safety limit is %d bytes.  You were about to ADD this to the repo.\n" % sizelimit)
  sys.stderr.write("See svnadmin/hooks/scripts/sizelimit.py for instructions if this is intended.\n")
  sys.exit(1)

if __name__ == "__main__":
  assert len(sys.argv) == 4
  core.run_app(checksize, sys.argv[1], sys.argv[2], int(sys.argv[3]))
