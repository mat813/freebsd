#! /bin/sh
# $FreeBSD$

TZ=UTC
export TZ

REPO="$1"
REV="$2"

if [ -z "$REV" -o -z "$REPO" -o ! -d "$REPO" ]; then
  echo "Bad args: repo rev" 1>&2
  exit 1
fi

PR="$(svnlook info "$REPO" -r "$REV" | sed -nE -e 's/^[ 	]*[pP][rR]:[ 	]*[a-zA-Z]+\/([0-9]+)/\1/p' -e 's/^[ 	]*[pP][rR]:[ 	]*([0-9]+)/\1/p')"

if [ -z "$PR" ]; then
  exit 0
fi
WHO="$(svnlook author "$REPO" -r "$REV")"

(
echo "From: commit-hook@freebsd.org"
echo "To: notify-bz@freebsd.org"
echo "Subject: [Bug $PR]"
echo ""
echo "A commit references this bug:"
echo ""
echo "Author: $WHO"
echo "Date: $(date)"
echo "New revision: $REV"
echo "URL: http://svnweb.freebsd.org/changeset/base/$REV"
echo ""
echo "Log:"
svnlook log "$REPO" -r "$REV" | sed -e 's/^/  /'
echo ""
echo "Changes:"
svnlook changed "$REPO" -r "$REV" | sed -E -e 's/^[A-Z]*[ 	]+/  /'
) | sed -e 's/^[ 	]*$//' | cat -s | /usr/sbin/sendmail -oi -f commit-hook@freebsd.org notify-bz@freebsd.org
