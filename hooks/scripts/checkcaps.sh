#! /bin/sh
# $FreeBSD$

CAPS="$1"

OIFS="$IFS"
IFS=":"
set $CAPS
IFS="$OIFS"

# atomic-revprops = 1.7+ client with improved mergeinfo handling
found=0
for i in $*
do
  case "$i" in
  "mergeinfo")
     found=1
     ;;
  esac
done

if [ $found = 0 ]
then
  echo "Please only do commits with a mergeinfo capable client" 1>&2
  echo "Currently this means svn-1.5 or later." 1>&2
  exit 1
fi
