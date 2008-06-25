/*
 * Ok, so this isn't exactly pretty, so sue me.
 *
 * The basic idea is to filter the arguments, check that everything
 * is happy, then give the appropriate privs, and exec the real svnserve.
 *
 * Installed setuid-root, grants the appropriate gid, then revokes setuid.
 * We use this in a NIS override.  ie:
 *   +:*::::::::/usr/local/bin/svnssh
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
#include <syslog.h>
#include <fcntl.h>

#define SVNROOT		"/s/svn"
#define BASEACCESS	SVNROOT "/base/conf/access"
/* Access cvs access files over nfs for now */
#define DOCACCESS	"/home/dcvs/CVSROOT/access"
#define PORTSACCESS	"/home/pcvs/CVSROOT/access"

#define NOCOMMIT	"/etc/nocommit"

static const char *env[] = {
	"PATH=" _PATH_DEFPATH,
	"SHELL=" _PATH_BSHELL,
	"HOME=/",
	NULL
};

static char username[32];
static char linebuf[1024];

static void
msg(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	fprintf(stderr, "\n");
	va_end(ap);
}

static void
usage(void)
{
	msg("Only the \"svnserve -t\" command is available.");
	exit(1);
}

static void
shell(char *argv[], int interactive)
{
	const char *sh = "/bin/tcsh";

	if (interactive)
		printf("Shell access granted - but you've got %s\n\n", sh);
	setuid(getuid());
	syslog(LOG_INFO, "shell access granted: %s", username);
	execv(sh, argv);
	msg("could not exec %s", sh);
	exit(1);
}

static int
karmacheck(FILE *fp, char *name)
{
	char buf[1024];
	char *p, *s;
	int karma;

	karma = 0;
	while ((p = fgets(buf, sizeof(buf) - 1, fp)) != NULL) {
		while ((s = strsep(&p, " \t\n")) != NULL) {
			if (*s == '\0')
				continue;	/* whitespace */
			if (*s == '#' || *s == '/' || *s == ';')
				break;		/* comment */
			if (strcmp(s, "*") == 0) {	/* all */
				karma++;
				break;
			}
			if (strcmp(s, name) == 0) {
				karma++;
				break;
			}
			break;	/* ignore further tokens on line */
		}
	}
	return karma;
}

int
main(int argc, char *argv[])
{
	struct passwd *pw;
	struct group *gr;
	struct stat st;
	struct rlimit rl;
	FILE *fp;
	int i;
	gid_t repogid;
	gid_t mygroups[NGROUPS_MAX];
	int ngroups;
	int karma;
	int shellkarma;

	umask(002);
	karma = 0;
	shellkarma = 0;
	openlog("svnssh", LOG_PID | LOG_NDELAY, LOG_AUTH);
	pw = getpwuid(getuid());
	if (pw == NULL) {
		msg("no user for uid %d", getuid());
		exit(1);
	}
	if (pw->pw_dir == NULL) {
		msg("no home directory");
		exit(1);
	}

	/* save in a static buffer */
	strlcpy(username, pw->pw_name, sizeof(username));

	ngroups = getgroups(NGROUPS_MAX, mygroups);
	if (ngroups > 0) {
		gr = getgrnam("shell");
		if (gr != NULL)
			for (i = 0; i < ngroups; i++)
				if (mygroups[i] == (gid_t)gr->gr_gid)
					shellkarma = 1;
	}
	if (argv[0][0] == '-' || argc == 1) {
		if (shellkarma)
			shell(argv, 1);
		syslog(LOG_INFO, "shell access denied: %s", username);
		msg("Sorry, no login shells on this machine.");
		usage();
	}

	if (argc != 3 || 
	    strcmp("svnssh",  argv[0]) != 0 ||
	    strcmp("-c",         argv[1]) != 0 ||
	    strcmp("svnserve -t", argv[2]) != 0) {
		if (shellkarma)		/* Allow any command */
			shell(argv, 0);
		syslog(LOG_INFO, "invalid args for svn server: %s, argc=%d", username, argc);
		msg("Invalid arguments for svnserve");
		fprintf(stderr, "You sent: argc=%d", argc);
		for (i = 0; i < argc; i++) {
			fprintf(stderr, " '%s'", argv[i]);
			syslog(LOG_INFO, "argv[%d] = %s", i, argv[i]);
		}
		fprintf(stderr, "\n");
		usage();
	}

	if (stat(SVNROOT, &st) < 0) {
		msg("Cannot stat %s", SVNROOT);
		exit(1);
	}
	repogid = st.st_gid;
	if (repogid < 10) {
		msg("unsafe repo gid %d\n", repogid);
		exit(1);
	}

	fp = fopen(NOCOMMIT, "r");
	if (fp != NULL) {
		msg("Sorry, commits temporarily locally disabled.");
		while (fgets(linebuf, sizeof(linebuf), fp) != NULL)
			fputs(linebuf, stderr);
		fclose(fp);
		exit(1);
	}

	fp = fopen(BASEACCESS, "r");
	if (fp == NULL) {
		msg("Cannot open %s", BASEACCESS);
		exit(1);
	} else {
		karma += karmacheck(fp, pw->pw_name);
		fclose(fp);
	}
#ifdef DOCACCESS
	/* Allow for failures due to NFS */
	if ((fp = fopen(DOCACCESS, "r")) != NULL) {
		karma += karmacheck(fp, pw->pw_name);
		fclose(fp);
	}
#endif
#ifdef PORTSACCESS
	/* Allow for failures due to NFS */
	if ((fp = fopen(PORTSACCESS, "r")) != NULL) {
		karma += karmacheck(fp, pw->pw_name);
		fclose(fp);
	}
#endif

	if (karma > 0) {
		/* set up read/write */
		if (setgid(repogid) < 0) {
			msg("setgid(%d) failed!", repogid);
			exit(1); 
		}
	}

	/* revoke suid-root */
	if (setuid(getuid()) < 0) {
		msg("setuid(%d) failed!", getuid());
		exit(1);
	}
	/* sanity check */
	if (getuid() < 10) {
		msg("root not allowed to commit");
		exit(1);
	}
	rl.rlim_cur = 540;	/* 9 minutes (soft) */
	rl.rlim_max = 600;	/* 10 minutes (hard) */
	setrlimit(RLIMIT_CPU, &rl);
	if (karma == 0)
		syslog(LOG_INFO, "svn server: %s, karma %d", username, karma);
	closelog();

	if (karma > 0)
		execle("/usr/local/bin/svnserve", "svnserve", "-t", "-r", SVNROOT, NULL, env);
	else
		execle("/usr/local/bin/svnserve", "svnserve", "-t", "-r", SVNROOT, "-R", NULL, env);
	err(1, "execle: svnserve");
}
