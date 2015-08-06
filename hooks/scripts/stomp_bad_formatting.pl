#!/usr/bin/perl -w
#
# $FreeBSD$

use strict;
my $debug = 0;

# $ svnlook changed /home/svnmirror/base -r 12348
# UU  head/sbin/mountd/mountd.c
# UU  head/usr.sbin/mountd/mountd.c
# $ svnlook log /home/svnmirror/base -r 12348
# Avoid bogus free() of a junk pointer.
#
# Detected by: phkmalloc
# Submitted by:   grog@lemis.de (Greg Lehey)
#
# Except that when called to vette a commit, it'll be "-t txn", not "-r rev"


my $repo = $ARGV[0];
my $txn = $ARGV[1];

my $log = "";

open(LOG, "svnlook log $repo -t $txn |") || die "cannot open svnlook log: $!";
foreach (<LOG>) {
	print "$$: log: $_" if ($debug);
	$log .= $_;
}
close(LOG);

if (stomp_bad_formatting($log)) {
	exit 1;
}
exit 0;

# ============================================================
# Look for a few specific mangled/broken template cases as a
# stopgap for checking for a proper template.

sub stomp_bad_formatting {
	my ($log) = @_;
	my $rv = 0;
	if ($log =~ m|\n\nReviewers:[\t ]+|s) {
		printf STDERR "**** Non-standard/badly formatted template - found 'Reviewers:' instead of 'Reviewed by:'.\n";
		$rv = 1;
	}
	# There is really no need for this spam in log messages.
	if ($log =~ m|\n\nSubscribers:[\t ]+|s) {
		printf STDERR "**** Non-standard/badly formatted template - found 'Subscribers:'.\n";
		$rv = 1;
	}
	$rv;
}
