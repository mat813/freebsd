#!/usr/bin/perl -w
#
# $FreeBSD$
#
# This script checks the paths touched in a pre-commit transaction against
# a whitelist of paths allowed in the repository.  This, along with other
# pre-commit scripts replace the "authz" mechanism.

use strict;
my $debug = 0;

# $ svnlook changed /home/svnmirror/base -r 12348
# UU  head/sbin/mountd/mountd.c
# UU  head/usr.sbin/mountd/mountd.c
#
# Except that when called to vette a commit, it'll be "-t txn", not "-r rev"


my $repo = $ARGV[0];
my $txn = $ARGV[1];

my @paths;

open(FILES, "svnlook changed $repo -t $txn |") || die "cannot open svnlook files: $!";
while (<FILES>) {
	chomp;
	my ($junk, $file) = split;
	print "$$: files_file: file=$file\n" if ($debug);
	push @paths, $file;
}
close(FILES);

if (check_paths(@paths)) {
	exit 1;
}
exit 0;

# ============================================================
sub read_paths {
	my @OK_Paths;
	my $paths_file = "$repo/conf/paths";
	if (-r $paths_file) {
		print "$$: Read $paths_file\n" if ($debug);
		if (not open(PATHS, "<$paths_file")) {
			print "$$: Cannot open paths file ($!).\n";
			return;
		}
		while (<PATHS>) {
			chomp;
			next if (/^#/);
			my $path = $_;
			if ($path) {
				push @OK_Paths, $path;
			}
		}
		close(PATHS);
	} else {
		print "$$: Cannot open paths file.\n";
	}
	@OK_Paths;
}

sub check_paths {
	my (@files) = @_;
	my @Paths = &read_paths();
	my $fails = 0;
file:
	foreach my $file (@files) {
		# check to see if file is allowed
		printf "$$: checking file: %s\n", $file if ($debug);
		foreach my $path (@Paths) {
			printf "$$: checking: %s\n", $path if ($debug);
			if ($file =~ m|$path|) {
				printf "$$: %s is allowed by %s\n", $file, $path if ($debug);
				next file;
			}
		}
		printf STDERR "**** File path \"%s\" is not allowed by $repo/conf/paths\n", $file;
		$fails++;
	}
	return $fails;
}
