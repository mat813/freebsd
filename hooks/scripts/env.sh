# source this file
# $FreeBSD$
PATH=/s/svn/base/hooks/scripts:/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin:/usr/local/sbin
export PATH
cd /s/svn/base
umask 002
if [ -x /usr/local/bin/checkacl-base ]; then
  eval `/usr/local/bin/checkacl-base base`
elif [ -x /usr/local/bin/checkacl ]; then
  eval `/usr/local/bin/checkacl base`
fi
