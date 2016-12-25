OBJ = coord.o for.o frame.o grap.o grapl.o input.o label.o main.o misc.o \
	plot.o print.o ticks.o version.o

FLAGS = -DLIBDIR='"$(LIBDIR)"' $(DEFINES) -I../include

YFLAGS = -d

.c.o:
	$(CC) $(_CFLAGS) $(FLAGS) -c $<

all: grap.c grapl.c grap grap.1

grap: $(OBJ)
	$(CC) $(_CFLAGS) $(_LDFLAGS) $(OBJ) $(LIBS) -lm -o grap

y.tab.h: grap.c

install:
	$(INSTALL) -c grap $(ROOT)$(BINDIR)/grap
	$(STRIP) $(ROOT)$(BINDIR)/grap
	test -d $(ROOT)$(LIBDIR) || mkdir -p $(ROOT)$(LIBDIR)
	$(INSTALL) -c -m 644 grap.defines $(ROOT)$(LIBDIR)/grap.defines
	$(INSTALL) -c -m 644 grap.1 $(ROOT)$(MANDIR)/man1/grap.1

clean:
	rm -f $(OBJ) grapl.c grap.c y.tab.h grap core log *~ grap.1

mrproper: clean

grap.1: grap.1.in
	sed 's"/usr/ucblib/"$(ROOT)$(LIBDIR)/"' grap.1.in > $@

coord.o: coord.c grap.h y.tab.h
for.o: for.c grap.h y.tab.h
frame.o: frame.c grap.h y.tab.h
grap.o: grap.c grap.h
grapl.o: grapl.c grap.h y.tab.h
input.o: input.c grap.h y.tab.h
label.o: label.c grap.h y.tab.h
main.o: main.c grap.h y.tab.h
misc.o: misc.c grap.h y.tab.h
plot.o: plot.c grap.h y.tab.h
print.o: print.c grap.h y.tab.h
ticks.o: ticks.c grap.h y.tab.h
