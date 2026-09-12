#include <mach-o/dyld.h>
#include <limits.h>
#include <libgen.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    char executable[PATH_MAX], resolved[PATH_MAX], python[PATH_MAX];
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size) || !realpath(executable, resolved)) return 1;
    for (int i = 0; i < 4; i++) {
        char *slash = strrchr(resolved, '/');
        if (!slash) return 1;
        *slash = '\0';
    }
    if (chdir(resolved)) { perror("Wild-Locate project directory"); return 1; }
    snprintf(python, sizeof(python), "%s/.venv/bin/python", resolved);
    const char *code =
        "import os,stat,sysconfig,runpy\n"
        "from pathlib import Path\n"
        "p=Path(sysconfig.get_path('purelib'))\n"
        "q=p/'PyQt6/Qt6/plugins'\n"
        "for f in [*p.glob('*.pth'),q,*q.rglob('*')]:\n"
        " if f.exists():\n"
        "  flags=f.stat().st_flags\n"
        "  if flags & stat.UF_HIDDEN: os.chflags(f,flags & ~stat.UF_HIDDEN)\n"
        "runpy.run_module('wildlocate',run_name='__main__')\n";
    execl(python, python, "-c", code, (char *)NULL);
    perror("Wild-Locate Python runtime");
    return 1;
}
