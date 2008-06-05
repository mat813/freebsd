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
my @paths;

open(LOG, "svnlook log $repo -t $txn |") || die "cannot open svnlook log: $!";
foreach (<LOG>) {
	print "$$: log: $_" if ($debug);
	$log .= $_;
}
close(LOG);

open(FILES, "svnlook changed $repo -t $txn |") || die "cannot open svnlook files: $!";
while (<FILES>) {
	chomp;
	#my ($junk, $file) = split(/\t/, $_, 2);
	my ($junk, $file) = split;
	print "$$: files_file: file=$file\n" if ($debug);
	push @paths, $file;
}
close(FILES);

if (check_approvers($log, @paths)) {
	exit 1;
}
exit 0;

# ============================================================
sub read_approvers {
	my @Approvers;
	my $approvers = "$repo/conf/approvers";
	if (-r $approvers) {
		print "$$: Read $approvers\n" if ($debug);
		if (not open(APP, "<$approvers")) {
			print "$$: Cannot open approvers file ($!).\n";
			return;
		}
		while (<APP>) {
			chomp;
			next if (/^#/);
			my ($path, $rev) = split(/\t+/, $_, 2);
			if ($rev) {
				push @Approvers, { path => $path,
						   app => $rev };
			}
		}
		close(APP);
	} else {
		print "$$: Cannot open approvers file.\n";
	}
	@Approvers;
}

sub check_approvers {
	my ($log, @files) = @_;
	my @Approvers = &read_approvers();
	foreach my $r (@Approvers) {
		printf "$$: checking: %s, %s\n",
			$r->{path}, $r->{app} if ($debug);
		foreach my $file (@files) {
			return 1 if (check_one($log, $r, $file));
		}
	}
	0;
}

sub check_one {
	my ($log, $r, $file) = @_;
	if ($file !~ m|$r->{path}|) {
		printf "$$: file not matched (%s, %s)\n", $file, $r->{path}
			if ($debug);
		return 0;
	}
	printf "$$: file matched (%s, %s)\n", $file, $r->{path} if ($debug);
	if ($log =~ m|Approved by:[\t ]*$r->{app}|s) {
		printf "$$: log matched (%s, %s)\n", $log, $r->{app}
			if ($debug);
		return 0;
	}
	printf "$$: log not matched (%s, %s)\n", $log, $r->{app} if ($debug);
	printf STDERR "**** You need \"Approved by: %s\" line in your log entry.\n",
		$r->{app};
	return 1;
}
