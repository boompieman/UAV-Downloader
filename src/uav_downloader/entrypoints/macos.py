"""Self-contained Mac application and early native-worker dispatcher."""
from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
import sys


def main():
    multiprocessing.freeze_support()
    if sys.argv[1:2] == ['--uav-native-worker']:
        from uav_downloader.subtitles.native_sherpa import main as worker
        return worker(sys.argv[2:])
    os.chdir(Path.home())
    from uav_downloader.core.bootstrap import (
        install_runtime_guards, run_translation_diagnostic_if_requested)
    install_runtime_guards()
    run_translation_diagnostic_if_requested()
    if sys.argv[1:2] == ['--uav-bundle-check']:
        from uav_downloader.core.macos_check import main as check
        return check(sys.argv[2:])
    from uav_downloader.core import config
    if not any(arg in ('-o', '--output') or arg.startswith('--output=')
               for arg in sys.argv[1:]):
        destination = config.get_download_directory() or str(Path.home() / 'Downloads' / 'UAV Downloader')
        sys.argv.extend(['--output', destination])
    from uav_downloader.entrypoints.browse import main as browser
    return browser()


if __name__ == '__main__':
    raise SystemExit(main())
