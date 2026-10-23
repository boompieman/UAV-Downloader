from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from uav_downloader.ui import player


def test_player_passes_unicode_and_option_like_names_without_a_shell(monkeypatch, tmp_path):
    path = tmp_path / '--日語 測試.mp4'
    path.touch()
    captured = {}
    process = SimpleNamespace(wait=lambda: 0)

    def popen(args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return process

    monkeypatch.setattr(player, 'find_mpv', lambda: '/mpv')
    monkeypatch.setattr(player.subprocess, 'Popen', popen)
    assert player.launch_player([path]) is process
    args = captured['args']
    assert args[-2:] == ['--', str(path)]
    assert '--hwdec=auto' in args
    assert '--sub-auto=exact' in args
    assert '--no-config' in args
    assert not captured['kwargs'].get('shell')


@pytest.mark.parametrize('paths', [[], ['https://example.com/video.mp4'], ['missing.mp4']])
def test_player_rejects_nonexistent_or_remote_inputs_before_spawning(monkeypatch, paths):
    monkeypatch.setattr(player.subprocess, 'Popen',
                        lambda *_args, **_kwargs: pytest.fail('must not start'))
    with pytest.raises(ValueError):
        player.launch_player(paths)


def test_player_missing_dependency_gives_install_instruction(monkeypatch):
    monkeypatch.setattr(player.shutil, 'which', lambda _name: None)
    monkeypatch.setattr(Path, 'is_file', lambda _path: False)
    with pytest.raises(FileNotFoundError, match='brew install mpv'):
        player.find_mpv()


def test_completed_and_local_rows_resolve_the_actual_file(tmp_path):
    path = tmp_path / 'title.mp4'
    path.touch()
    item = SimpleNamespace(local=False, dest=str(tmp_path), name='title')
    assert player.downloaded_video_path(item) == path
    item.name = '../title'
    assert player.downloaded_video_path(item) is None
    item.local, item.url = True, str(path)
    assert player.downloaded_video_path(item) == path
    path.unlink()
    assert player.downloaded_video_path(item) is None


def test_download_play_action_uses_the_row_destination(monkeypatch, tmp_path):
    from uav_downloader.apps import browse
    path = tmp_path / 'title.mp4'
    path.touch()
    item = SimpleNamespace(local=False, url='source', dest=str(tmp_path), name='title')
    played = []
    app = SimpleNamespace(_dlmgr=SimpleNamespace(get_items=lambda: [item]),
                          _play_videos=lambda paths: played.extend(paths))
    browse.ModernApp._play_download(app, 'source')
    assert played == [path]


def test_decoder_failure_is_reported_to_the_caller(monkeypatch, tmp_path):
    path = tmp_path / 'broken.mp4'
    path.touch()
    notified = threading.Event()
    messages = []

    def popen(_args, **kwargs):
        kwargs['stderr'].write(b'Cannot decode video')
        kwargs['stderr'].flush()
        return SimpleNamespace(wait=lambda: 1)

    def failed(message):
        messages.append(message)
        notified.set()

    monkeypatch.setattr(player, 'find_mpv', lambda: '/mpv')
    monkeypatch.setattr(player.subprocess, 'Popen', popen)
    player.launch_player([path], on_error=failed)
    assert notified.wait(2)
    assert messages == ['Cannot decode video']


def test_independent_player_picker_cancel_starts_no_process(monkeypatch):
    import tkinter
    from tkinter import filedialog
    destroyed = []
    monkeypatch.setattr(tkinter, 'Tk', lambda: SimpleNamespace(
        withdraw=lambda: None, destroy=lambda: destroyed.append(True)))
    monkeypatch.setattr(filedialog, 'askopenfilenames', lambda **_kwargs: ())
    monkeypatch.setattr(player, 'launch_player',
                        lambda *_args, **_kwargs: pytest.fail('Picker was cancelled'))
    assert player.main([]) == 0
    assert destroyed == [True]
