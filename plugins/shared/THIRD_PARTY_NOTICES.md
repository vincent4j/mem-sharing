# Third-party runtime notices

These tools are downloaded, after a separate host confirmation, as unchanged original archives from their official release URLs. The plugin does not embed or repackage the runtime binaries. Download size and SHA256 are fixed in `server/shared/common/production-assets.ts`. Extracted runtimes persist in the user-owned mem-sharing-runtimes directory independently of the plugin.

This disclosure provides the named core project licenses and fixed build-definition references. It does not claim a complete transitive SBOM or a file-by-file binary license audit. Original archive notices remain in the installed runtime.

## CPython 3.13.18 / python-build-standalone 20261026

Build source: https://github.com/astral-sh/python-build-standalone/tree/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee
CPython source and license: https://github.com/python/cpython/tree/v3.13.18 and https://github.com/python/cpython/blob/v3.13.18/LICENSE

Fixed build definitions:

- https://github.com/astral-sh/python-build-standalone/blob/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/cpython-unix/targets.yml
- https://github.com/astral-sh/python-build-standalone/blob/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/cpython-unix/extension-modules.yml
- https://github.com/astral-sh/python-build-standalone/blob/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/pythonbuild/downloads.json
- https://github.com/astral-sh/python-build-standalone/blob/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/cpython-unix/build-cpython.sh

The inspected install_only_stripped archives contain `python/lib/python3.13/LICENSE.txt` and pip/vendor licenses. They do not contain `PYTHON.json` or the full build output licenses directory. The copies below supplement that disclosure; their presence does not assert that every referenced dependency is included in this target binary.

Build-module references: bzip2 -> _bz2; expat -> pyexpat; libffi -> _ctypes; mpdecimal -> _decimal; OpenSSL -> _ssl/_hashlib; SQLite -> _sqlite3; xz -> _lzma. The inspected package includes _tkinter and Tcl/Tk 9 dynamic libraries; the Tcl license is included below. libuuid and zstd are build-source references, not assertions of included runtime code (the _zstd module requires Python 3.14 and this runtime is 3.13). The fixed macOS build uses system zlib, libedit, ncurses and panel; their /usr/lib dependencies are supplied by macOS and are not redistributed in these archives (build-cpython.sh, extension-modules.yml and local otool inspection).

Exact source archives recorded by the fixed build definition:

- bzip2: https://sourceware.org/pub/bzip2/bzip2-1.0.8.tar.gz
- expat: https://github.com/libexpat/libexpat/releases/download/R_2_9_0/expat-2.9.0.tar.xz
- libffi: https://github.com/libffi/libffi/releases/download/v3.8.0/libffi-3.8.0.tar.gz
- mpdecimal: https://www.bytereef.org/software/mpdecimal/releases/mpdecimal-4.0.0.tar.gz
- openssl-3.5: https://github.com/openssl/openssl/releases/download/openssl-3.5.9/openssl-3.5.9.tar.gz
- sqlite: https://www.sqlite.org/2026/sqlite-autoconf-3530100.tar.gz
- tcl: https://prdownloads.sourceforge.net/tcl/tcl9.0.4-src.tar.gz
- tk: https://prdownloads.sourceforge.net/tcl/tk9.0.4-src.tar.gz
- xz: https://github.com/tukaani-project/xz/releases/download/v5.8.4/xz-5.8.4.tar.gz
- zstd: https://github.com/python/cpython-source-deps/archive/refs/tags/zstd-1.5.7.tar.gz

## Git 2.56.0 / dugite-native v2.56.0-2

Build/package source: https://github.com/desktop/dugite-native/tree/a44aeca2f8593510c8080d8b7767468fa210a02c
Fixed dependencies: https://github.com/desktop/dugite-native/blob/a44aeca2f8593510c8080d8b7767468fa210a02c/dependencies.json
Git corresponding source: https://github.com/git/git/tree/a018953688f1b10bddf91bff8747068f5f4746a4
Git LFS v3.8.1 source: https://github.com/git-lfs/git-lfs/tree/a662a6dbfedf706cfa9fc7a5b7bcc7ba2e2c8a65
Git Credential Manager v2.9.1 source: https://github.com/git-ecosystem/git-credential-manager/tree/6760f0ef069c994aa2bb1d703fb374986ee82a3e

The inspected Git archives include `libexec/git-core/NOTICE` from GCM (GitHub/VisualStudio and dotnet/runtime notices), but do not include Git COPYING, Git LFS LICENSE or GCM LICENSE. Their fixed upstream texts are supplied below. macOS Git and its HTTP helper dynamically reference system libraries; the bundled GCM/.NET/Avalonia tree is retained unchanged. This notice does not claim exhaustive transitive dependency coverage.

## Fixed official original archives

- https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.13.18%2B20261026-aarch64-apple-darwin-install_only_stripped.tar.gz (SHA256 8392b6ea51d94391befb2c31ebe75463f045d0b69dfcf5e1bb3234e1f5fa3405)
- https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.13.18%2B20261026-x86_64-apple-darwin-install_only_stripped.tar.gz (SHA256 7412c19d896c99431b74a18a5643e110449a7f9590fbab179c3e5ab27b9aa9e3)
- https://github.com/desktop/dugite-native/releases/download/v2.56.0-2/dugite-native-v2.56.0-a44aeca-macOS-arm64.tar.gz (SHA256 1110de343de11cc6f469b782b60f36217b9199b5e06875dd65baa26dd60563c7)
- https://github.com/desktop/dugite-native/releases/download/v2.56.0-2/dugite-native-v2.56.0-a44aeca-macOS-x64.tar.gz (SHA256 52cc663281e1ec2f1d76ba781193ca4847e62dbbf767f6c99ec9ec5b978a7659)

## License text copies and their fixed upstream sources

- [git-COPYING.txt](notices/git-COPYING.txt) — https://raw.githubusercontent.com/git/git/a018953688f1b10bddf91bff8747068f5f4746a4/COPYING
- [git-lfs-LICENSE.txt](notices/git-lfs-LICENSE.txt) — https://raw.githubusercontent.com/git-lfs/git-lfs/a662a6dbfedf706cfa9fc7a5b7bcc7ba2e2c8a65/LICENSE.md
- [gcm-LICENSE.txt](notices/gcm-LICENSE.txt) — https://raw.githubusercontent.com/git-ecosystem/git-credential-manager/6760f0ef069c994aa2bb1d703fb374986ee82a3e/LICENSE
- [gcm-NOTICE.txt](notices/gcm-NOTICE.txt) — https://raw.githubusercontent.com/git-ecosystem/git-credential-manager/6760f0ef069c994aa2bb1d703fb374986ee82a3e/NOTICE
- [dugite-license.txt](notices/dugite-license.txt) — https://raw.githubusercontent.com/desktop/dugite-native/a44aeca2f8593510c8080d8b7767468fa210a02c/LICENSE.md
- [pybs-LICENSE.bzip2.txt.txt](notices/pybs-LICENSE.bzip2.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.bzip2.txt
- [pybs-LICENSE.cpython.txt.txt](notices/pybs-LICENSE.cpython.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.cpython.txt
- [pybs-LICENSE.expat.txt.txt](notices/pybs-LICENSE.expat.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.expat.txt
- [pybs-LICENSE.libedit.txt.txt](notices/pybs-LICENSE.libedit.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.libedit.txt
- [pybs-LICENSE.libffi.txt.txt](notices/pybs-LICENSE.libffi.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.libffi.txt
- [pybs-LICENSE.liblzma.txt.txt](notices/pybs-LICENSE.liblzma.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.liblzma.txt
- [pybs-LICENSE.libuuid.txt.txt](notices/pybs-LICENSE.libuuid.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.libuuid.txt
- [pybs-LICENSE.mpdecimal.txt.txt](notices/pybs-LICENSE.mpdecimal.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.mpdecimal.txt
- [pybs-LICENSE.openssl-3.txt.txt](notices/pybs-LICENSE.openssl-3.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.openssl-3.txt
- [pybs-LICENSE.sqlite.txt.txt](notices/pybs-LICENSE.sqlite.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.sqlite.txt
- [pybs-LICENSE.tcl.txt.txt](notices/pybs-LICENSE.tcl.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.tcl.txt
- [pybs-LICENSE.zstd.txt.txt](notices/pybs-LICENSE.zstd.txt.txt) — https://raw.githubusercontent.com/astral-sh/python-build-standalone/fa506e0858ac9f2cc5b289c137b888a2aa24d1ee/LICENSE.zstd.txt
