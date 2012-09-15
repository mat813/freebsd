/*
 * Ok, so this isn't exactly pretty, so sue me.
 *
 * FreeBSD Subversion tree ACL check helper.  The program looks in
 * relevant access files to find out if the committer may commit.
 *
 * !!! Please keep in sync between various SVN repositories. !!!
 *
 * From: Id: cvssh.c,v 1.38 2008/05/31 02:54:58 peter Exp
 * $FreeBSD$
 */

#include <sys/param.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <stdio.h>
#include <stdlib.h>
#include <paths.h>
#include <pwd.h>
#include <grp.h>
#include <unistd.h>
#include <string.h>
#include <err.h>
#include <signal.h>
#include <stdarg.h>
#include <fcntl.h>

#define	BASE		0x01
#define	DOC		0x02
#define	PORTS		0x04

#define	SVNROOT		"/s/svn"
#define	BASEACCESS	SVNROOT "/base/conf/access"
#define	DOCACCESS	SVNROOT "/doc/conf/access"
#define	PORTSACCESS	SVNROOT "/ports/conf/access"

static char username[_SC_LOGIN_NAME_MAX + 1];

static void
msg(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	fprintf(stderr, "\n");
	va_end(ap);
}

static u_int
karmacheck(FILE *fp, const char *name, u_int k)
{
	char buf[1024];
	char *p, *s;
	u_int karma;

	karma = 0;
	while ((p = fgets(buf, sizeof(buf) - 1, fp)) != NULL) {
		while ((s = strsep(&p, " \t\n")) != NULL) {
			if (*s == '\0')
				continue;	/* whitespace */
			if (*s == '#' || *s == '/' || *s == ';')
				break;		/* comment */
			if (strcmp(s, "*") == 0) {	/* all */
				karma |= k;
				break;
			}
			if (strcmp(s, name) == 0) {
				karma |= k;
				break;
			}
			break;	/* ignore further tokens on line */
		}
	}
	return karma;
}

static u_int
read_access(const char *accessf, const u_int repo, u_int k,
    const char *name)
{
	FILE *fp;
	u_int karma;

	karma = 0;
	fp = fopen(accessf, "r");
	if (fp == NULL && (repo & k) == k) {
		msg("Cannot open %s", accessf);
		exit(1);
	} else if (fp != NULL) {
		karma |= karmacheck(fp, name, k);
		fclose(fp);
	}

	return (karma);
}

static void
catcommittag(char *committag, const char **comma, const u_int karma,
    const u_int k, const char *s)
{

	if ((karma & k) == 0)
		return;

	strcat(committag, *comma);
	strcat(committag, s);
	*comma = ",";
}

int
main(int argc, char *argv[])
{
	struct passwd *pw;
	struct stat st;
	gid_t repogid;
	gid_t mygroups[NGROUPS_MAX];
	int i, ngroups, writeable;
	u_int karma, repo;

	pw = getpwuid(getuid());
	if (pw == NULL) {
		msg("no user for uid %d", getuid());
		exit(1);
	}
	if (pw->pw_dir == NULL) {
		msg("no home directory");
		exit(1);
	}

	/* Save in a static buffer. */
	strlcpy(username, pw->pw_name, sizeof(username));
	endpwent();

	if (stat(SVNROOT, &st) < 0) {
		msg("Cannot stat %s", SVNROOT);
		exit(1);
	}
	repogid = st.st_gid;
	if (repogid < 10) {
		msg("unsafe repo gid %d\n", repogid);
		exit(1);
	}
	writeable = 0;
	ngroups = getgroups(NGROUPS_MAX, mygroups);
	if (ngroups > 0) {
		for (i = 0; i < ngroups; i++)
			if (mygroups[i] == repogid)
				writeable = 1;
	}
	if (!writeable)
		printf("export SVN_READONLY=y\n");

        if (argc != 2) {
		msg("No repository given");
		exit(1);
	}
	repo = 0;
	/* Forward compat for base. */
	if (strcmp(argv[1], "base") == 0 || strcmp(argv[1], "src") == 0)
		 repo |= BASE;
	else if (strcmp(argv[1], "doc") == 0)
		repo |= DOC;
	else if (strcmp(argv[1], "ports") == 0)
		repo |= PORTS;
	else {
		msg("Invalid repository given: %s", argv[1]);
		exit(1);
	}

	karma = 0;
#ifdef BASEACCESS
	karma |= read_access(BASEACCESS, repo, BASE, username);
#endif
#ifdef DOCACCESS
	karma |= read_access(DOCACCESS, repo, DOC, username);
#endif
#ifdef PORTSACCESS
	karma |= read_access(PORTSACCESS, repo, PORTS, username);
#endif
	if (karma == 0) {
		/* If still zero, its a readonly access */
		printf("export SVN_READONLY=y\n");

	} else if ((repo & karma) == 0) {
		char committag[sizeof("src,doc,ports") + 1];
		const char *comma;

		committag[0] = '\0';
		comma = "";
		catcommittag(committag, &comma, karma, BASE, "src");
		catcommittag(committag, &comma, karma, DOC, "doc");
		catcommittag(committag, &comma, karma, PORTS, "ports");
		printf("export SVN_COMMIT_ATTRIB=\"%s\"\n", committag);
	}
		
	return (0);
}
