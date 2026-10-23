"""Offline acceptance check executed inside the relocated frozen Mac app."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args(argv)
    if not args.video.is_file() or args.video.resolve() == args.report.resolve():
        parser.error('Choose an existing video and a separate report path')
    from uav_downloader.sites import base
    from uav_downloader.subtitles import engine
    from uav_downloader.subtitles.settings import TranslationSettings
    from uav_downloader.ui import player
    root = Path(sys._MEIPASS).resolve()
    ffmpeg = base.locate_ffmpeg()
    mpv = player.find_mpv()
    assert Path(ffmpeg).resolve().is_relative_to(root)
    assert Path(mpv).resolve().is_relative_to(root)

    def no_download(*_args, **_kwargs):
        raise AssertionError('Bundled models must work without model downloads')

    engine._download_verified = no_download
    engine._selected_translation_profile = lambda: TranslationSettings()
    checks = {'frozen': bool(getattr(sys, 'frozen', False)),
              'bundled_ffmpeg': True, 'bundled_mpv': True}
    with tempfile.TemporaryDirectory(prefix='uav-app-check-') as temporary:
        work = Path(temporary)
        hls = work / 'hls'
        hls.mkdir()
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i',
                        str(args.video.resolve()), '-c', 'copy', '-f', 'hls',
                        '-hls_time', '2', str(hls / 'index.m3u8')], check=True, timeout=60)

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(hls)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            class LocalVideo(base.M3U8Crawler):
                @classmethod
                def validate_url(cls, _url):
                    return 'mac-bundle-check'

                def get_url_infos(self):
                    self._targetName = 'Japanese test'
                    self._m3u8url = self._url

            job = LocalVideo(f'http://127.0.0.1:{server.server_port}/index.m3u8',
                             str(work / 'downloads'), silence=True, max_workers=2)
            assert job.start_download()
            video = Path(job._get_video_savename())
            assert video.is_file() and video.stat().st_size > 0
            checks['hls_download_and_mp4_merge'] = True
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        for selection in ('parakeet', 'auto'):
            engine.config.get_recognition_quality = lambda value=selection: value
            result = engine.generate_subtitles(str(video), 'all')
            assert len(result.generated) == 3
            assert all(engine.parse_srt(Path(path).read_text(encoding='utf-8'))
                       for path in result.files)
            checks[selection + '_ja_en_zh_subtitles'] = True

        from uav_downloader.apps import browse
        browse.CSV_PATH = str(work / 'queue.csv')
        browse.config.get_ui_lang = lambda: 'zh'
        app = browse.ModernApp(dest=str(work / 'downloads'))
        try:
            app.update_idletasks()
            assert len(app._recognition_quality_values()) == 2
            checks['tk_gui'] = True
        finally:
            app._on_close()

        original_popen = player.subprocess.Popen

        def instrument(command, **kwargs):
            at = command.index('--')
            command[at:at] = ['--input-ipc-server=' + str(work / 'mpv.sock'), '--mute=yes']
            return original_popen(command, **kwargs)

        player.subprocess.Popen = instrument
        try:
            process = player.launch_player([video])
        finally:
            player.subprocess.Popen = original_popen
        try:
            deadline = time.monotonic() + 20
            while not (work / 'mpv.sock').exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise AssertionError('Bundled player did not start')
                time.sleep(.1)
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(5)
                connection.connect(str(work / 'mpv.sock'))
                stream = connection.makefile('rwb', buffering=0)

                def command(*values):
                    stream.write((json.dumps({'command': values, 'request_id': 9}) + '\n').encode())
                    for _index in range(100):
                        response = json.loads(stream.readline())
                        if response.get('request_id') == 9:
                            assert response['error'] == 'success', response
                            return response.get('data')
                    raise AssertionError('Player response limit exceeded')

                while not command('get_property', 'time-pos'):
                    if time.monotonic() > deadline:
                        raise AssertionError('Player did not decode frames')
                    time.sleep(.1)
                checks['hardware_decoder'] = command('get_property', 'hwdec-current')
                assert checks['hardware_decoder'] == 'videotoolbox'
                tracks = [track for track in command('get_property', 'track-list')
                          if track['type'] == 'sub']
                assert len(tracks) == 3
                for track in tracks:
                    command('set_property', 'sid', track['id'])
                    assert command('get_property', 'sid') == track['id']
                command('set_property', 'pause', True)
                assert command('get_property', 'pause') is True
                command('seek', 5, 'absolute')
                checks['play_pause_seek_and_three_subtitle_tracks'] = True
        finally:
            process.terminate()
            process.wait(timeout=10)
    args.report.write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
    return 0
