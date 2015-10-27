#!/usr/bin/env perl


# $FreeBSD$
# source: http://svn.collab.net/repos/svn/trunk/contrib/hook-scripts/check-mime-type.pl
#

# ====================================================================
# commit-mime-type-check.pl: check that every added file has the
# svn:mime-type property set and every added file with a mime-type
# matching text/* also has svn:eol-style set. If any file fails this
# test the user is sent a verbose error message suggesting solutions and
# the commit is aborted.
#
# Usage: commit-mime-type-check.pl REPOS TXN-NAME
# ====================================================================
# Most of commit-mime-type-check.pl was taken from
# commit-access-control.pl, Revision 9986, 2004-06-14 16:29:22 -0400.
# ====================================================================
# Copyright (c) 2000-2004 CollabNet.  All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.  The terms
# are also available at http://subversion.tigris.org/license.html.
# If newer versions of this license are posted there, you may use a
# newer version instead, at your option.
#
# This software consists of voluntary contributions made by many
# individuals.  For exact contribution history, see the revision
# history and logs, available at http://subversion.tigris.org/.
# ====================================================================

require warnings;
import warnings;

use v5.10; # earliest occurance of feature
no warnings 'experimental::smartmatch';

use strict;
use Carp;
use feature qw(switch);		# be 5.10 or later, or else!

######################################################################
# Configuration section.

######################################################################
# Initial setup/command-line handling.

&usage unless @ARGV == 3;

my $repos        = shift;
my $mode         = shift;
my $txn          = shift;

unless (-e $repos) {
  &usage("$0: repository directory `$repos' does not exist.");
}
unless (-d $repos) {
  &usage("$0: repository directory `$repos' is not a directory.");
}


######################################################################
# Harvest data using svnlook.

# Change into /tmp so that svnlook diff can create its .svnlook
# directory.
my $tmp_dir = '/tmp';
chdir($tmp_dir)
  or die "$0: cannot chdir `$tmp_dir': $!\n";


#see rev 257353.  We're trying to allow modifications but prevent new stuff.
#Property changes on: stable/10/etc
#___________________________________________________________________
#Modified: svn:mergeinfo
#
#Property changes on: stable/10/share/man/man7
#___________________________________________________________________
#Added: svn:mergeinfo

my $state = 0;
my $path;
my @errors;
foreach my $line (&read_from_process('svnlook', 'diff', $repos, $mode, $txn)) {
  #printf "line: %s, current state %d\n", $line, $state;
  if ($state == 0 && $line =~ /^Property changes on: (.*)$/) {
    $path = $1;
    given ($path) {
      when (/stable\/([0-9]+)\//) { if ($1 >= 10) { $state = 1; } else { $state = 0; } }
      default { $state = 0; }
    }
    #printf "path: %s, state %d\n", $path, $state;
    next;
  }
  if ($state == 1) {
    if ($line =~ /^___________/) { $state = 2; } else { $state = 0; }
    #print "state 1 -> 2\n";
    next;
  }
  if ($state == 2) {
    given ($line) {
      when (/^Added: svn:mergeinfo/) {
	push @errors, "$path : svn:mergeinfo ADDED";
      }
      when (/^================/) { $state = 0; }
    }
  }
}

# If there are any errors list the problem files and give information
# on how to avoid the problem. Hopefully people will set up auto-props
# and will not see this verbose message more than once.
if (@errors) {
    warn "$0:\n\n", join("\n", @errors), "\n\n", <<EOS;
    If you use "svn merge" then it must be done at the top level
    directory to prevent spread of mergeinfo records.  Resulting
    commits must ALSO be done from the root directory.

    This applies to the stable/10 or higher branches.

    This commit was aborted because it would have added NEW mergeinfo
    records elsewhere, somehow.

    merges with --ignore-ancestry or diff | patch do not require this.
EOS
  exit 1;
} else {
  exit 0;
}

sub usage
{
  warn "@_\n" if @_;
  die "usage: $0 REPOS [-r REV] | [-t TXN-NAME]\n";
}

sub safe_read_from_pipe
{
  unless (@_) {
    croak "$0: safe_read_from_pipe passed no arguments.\n";
  }
  #print "Running @_\n";
  my $pid = open(SAFE_READ, '-|');
  unless (defined $pid) {
    die "$0: cannot fork: $!\n";
  }
  unless ($pid) {
    open(STDERR, ">&STDOUT") || die "$0: cannot dup STDOUT: $!\n";
    exec(@_) || die "$0: cannot exec `@_': $!\n";
  }
  my @output;
  while (<SAFE_READ>) {
    chomp;
    push(@output, $_);
  }
  close(SAFE_READ);
  my $result = $?;
  my $exit   = $result >> 8;
  my $signal = $result & 127;
  my $cd     = $result & 128 ? "with core dump" : "";
  if ($signal or $cd) {
    warn "$0: pipe from `@_' failed $cd: exit=$exit signal=$signal\n";
  }
  if (wantarray) {
    return ($result, @output);
  } else {
    return $result;
  }
}

sub read_from_process
{
  unless (@_) {
    croak "$0: read_from_process passed no arguments.\n";
  }
  my ($status, @output) = &safe_read_from_pipe(@_);
  if ($status) {
    if (@output) {
      die "$0: `@_' failed with this output:\n", join("\n", @output), "\n";
    } else {
      die "$0: `@_' failed with no output.\n";
    }
  } else {
    return @output;
  }
}
