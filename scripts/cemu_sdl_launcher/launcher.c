/*
 * Tiny Mach-O launcher: set SDL mapping env, then exec the real Cemu binary (*.real).
 * CFBundleExecutable points here so Dock/Launchpad get the same env as launch_cemu.sh.
 */
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libgen.h>
#include <sys/stat.h>

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

static char *read_whole_file(const char *path, size_t *out_len) {
	FILE *f;
	char *buf;
	long n;

	*out_len = 0;
	f = fopen(path, "rb");
	if (!f)
		return NULL;
	if (fseek(f, 0, SEEK_END) != 0) {
		fclose(f);
		return NULL;
	}
	n = ftell(f);
	if (n < 0) {
		fclose(f);
		return NULL;
	}
	if (fseek(f, 0, SEEK_SET) != 0) {
		fclose(f);
		return NULL;
	}
	buf = (char *)malloc((size_t)n + 1);
	if (!buf) {
		fclose(f);
		return NULL;
	}
	if (n > 0 && fread(buf, 1, (size_t)n, f) != (size_t)n) {
		free(buf);
		fclose(f);
		return NULL;
	}
	fclose(f);
	buf[n] = '\0';
	/* trim trailing newlines */
	while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r'))
		buf[--n] = '\0';
	*out_len = (size_t)n;
	return buf;
}

static int get_exe_path(char *buf, size_t buflen) {
#ifdef __APPLE__
	uint32_t sz = (uint32_t)buflen;
	if (_NSGetExecutablePath(buf, &sz) == 0)
		return 0;
#endif
	return -1;
}

int main(int argc, char *argv[]) {
	char exe[PATH_MAX];
	char exe_copy[PATH_MAX];
	char res_dir[PATH_MAX];
	char real_exe[PATH_MAX];
	char mappings[PATH_MAX];
	char patches[PATH_MAX];
	char *inline_cfg = NULL;
	size_t inline_len = 0;
	struct stat st;

	(void)argc;

	if (get_exe_path(exe, sizeof exe) != 0) {
		fprintf(stderr, "cemu_sdl_launcher: cannot resolve executable path\n");
		return 1;
	}

	snprintf(exe_copy, sizeof exe_copy, "%s", exe);
	snprintf(real_exe, sizeof real_exe, "%s.real", exe);

	if (stat(real_exe, &st) != 0) {
		fprintf(stderr, "cemu_sdl_launcher: missing real binary: %s\n", real_exe);
		return 1;
	}

	/* .../Contents/MacOS/foo -> .../Contents/Resources */
	snprintf(res_dir, sizeof res_dir, "%s", exe_copy);
	{
		char *macos_dir = dirname(res_dir);
		char contents[PATH_MAX];
		snprintf(contents, sizeof contents, "%s/..", macos_dir);
		if (!realpath(contents, res_dir)) {
			fprintf(stderr, "cemu_sdl_launcher: cannot resolve Resources path\n");
			return 1;
		}
		strlcat(res_dir, "/Resources", sizeof res_dir);
	}

	snprintf(mappings, sizeof mappings, "%s/cemu_sdl_mappings.txt", res_dir);
	snprintf(patches, sizeof patches, "%s/cemu_sdl_patches_inline.txt", res_dir);

	if (stat(mappings, &st) == 0)
		setenv("SDL_GAMECONTROLLERCONFIG_FILE", mappings, 1);

	inline_cfg = read_whole_file(patches, &inline_len);
	if (inline_cfg && inline_len > 0)
		setenv("SDL_GAMECONTROLLERCONFIG", inline_cfg, 1);

	argv[0] = real_exe;
	execv(real_exe, argv);

	fprintf(stderr, "cemu_sdl_launcher: execv(%s): ", real_exe);
	perror(NULL);
	free(inline_cfg);
	return 1;
}
