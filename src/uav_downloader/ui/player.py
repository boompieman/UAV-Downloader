"""Local video playback through the upstream mpv player."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading


VIDEO_EXTENSIONS = frozenset({'.mp4', '.mkv', '.ts', '.mov', '.m4v', '.webm', '.avi', '.m2ts'})


def find_mpv() -> str:
    executable = shutil.which('mpv')
    if executable:
        return executable
    for path in ('/opt/homebrew/bin/mpv', '/usr/local/bin/mpv',
                 '/Applications/mpv.app/Contents/MacOS/mpv'):
        if Path(path).is_file():
            return path
    raise FileNotFoundError('mpv is required. On macOS, install it with: brew install mpv')


def downloaded_video_path(item) -> Path | None:
    if item.local:
        candidate = Path(item.url).expanduser()
    else:
        if not item.dest or not item.name or Path(item.name).name != item.name:
            return None
        candidate = Path(item.dest).expanduser() / (item.name + '.mp4')
    return candidate.resolve() if candidate.is_file() else None


def launch_player(paths, *, on_error=None):
    videos = [Path(path).expanduser().resolve() for path in paths]
    if not videos or any(not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS
                         for path in videos):
        raise ValueError('Select existing local video files')
    args = [
        find_mpv(), '--no-config', '--hwdec=auto', '--osc=yes',
        '--force-window=yes', '--keep-open=yes', '--sub-auto=exact',
        '--slang=zh-TW,zh,ja,en', '--title=UAV Player — ${media-title}',
        '--ytdl=no', '--save-position-on-quit=no', '--',
        *(str(path) for path in videos),
    ]
    errors = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=errors)
    except Exception:
        errors.close()
        raise

    def watch():
        try:
            if process.wait() and on_error:
                errors.seek(0, 2)
                errors.seek(max(0, errors.tell() - 8192))
                message = errors.read().decode('utf-8', errors='replace').strip()
                on_error(message or 'mpv could not play this video')
        finally:
            errors.close()

    threading.Thread(target=watch, daemon=True).start()
    return process


def main(argv=None):
    parser = argparse.ArgumentParser(description='Play local videos with UAV Player (mpv)')
    parser.add_argument('videos', nargs='*', help='Local video files; omit to choose files')
    args = parser.parse_args(argv)
    try:
        if not args.videos:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            try:
                args.videos = filedialog.askopenfilenames(
                    title='UAV Player — Open local videos',
                    filetypes=[('Videos', ' '.join('*' + ext for ext in sorted(VIDEO_EXTENSIONS)))])
            finally:
                root.destroy()
            if not args.videos:
                return 0
        return launch_player(args.videos, on_error=lambda message: print(message, file=sys.stderr)).wait()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
