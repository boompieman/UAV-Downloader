import hashlib
from pathlib import Path
import sys

import pytest

from uav_downloader.subtitles import engine
from uav_downloader.ui import player


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    monkeypatch.setattr(sys, 'platform', 'darwin')
    return tmp_path


def test_frozen_native_worker_reenters_the_app_instead_of_running_a_python_file(frozen):
    assert engine._native_sherpa_command() == [sys.executable, '--uav-native-worker']
    args = engine._reazonspeech_cli_args(
        '/pack', ['island-00000.wav'], native=True, ctc_model_dir='/model')
    assert args[:3] == [sys.executable, '--uav-native-worker', 'asr']


def test_frozen_player_uses_bundled_mpv_before_homebrew(frozen, monkeypatch):
    executable = frozen / 'player/mpv'
    executable.parent.mkdir()
    executable.touch()
    monkeypatch.setattr(player.shutil, 'which', lambda *_args: pytest.fail('No PATH lookup'))
    assert player.find_mpv() == str(executable)


@pytest.mark.parametrize('corrupt', [False, True])
def test_bundled_parakeet_is_verified_and_never_downloaded(frozen, monkeypatch, corrupt):
    model = frozen / 'components' / f'parakeet-ja-{engine.PARAKEET_MODEL_REVISION}'
    model.mkdir(parents=True)
    expected = {}
    for name in ('model.int8.onnx', 'tokens.txt'):
        data = name.encode()
        expected[name] = (len(data), hashlib.sha256(data).hexdigest())
        (model / name).write_bytes(b'broken' if corrupt else data)
    monkeypatch.setattr(engine, 'PARAKEET_MODEL_FILES', expected)
    monkeypatch.setattr(engine, '_download_verified',
                        lambda *_args: pytest.fail('No model download'))
    if corrupt:
        with pytest.raises(engine.SubtitleError, match='integrity'):
            engine._prepare_parakeet_model(None, None)
    else:
        assert engine._prepare_parakeet_model(None, None) == str(model)


def test_packaged_model_packs_are_found_inside_the_app(frozen):
    candidates = engine._component_install_candidates(engine.TRANSLATION_PACK_NAME)
    assert str(frozen / 'components' / Path(engine.TRANSLATION_PACK_NAME).stem) in candidates


def test_frozen_mac_logs_stay_outside_the_signed_bundle(frozen, monkeypatch, tmp_path):
    from uav_downloader.core import crashlog
    state = tmp_path / 'state'
    monkeypatch.setenv('APPDATA', str(state))
    directory = Path(crashlog._base_dir())
    assert directory.is_relative_to(state)
    assert directory.is_dir()


def test_native_worker_dispatch_happens_before_gui_or_runtime_guards(monkeypatch):
    pytest.importorskip('sherpa_onnx')
    from uav_downloader.entrypoints import macos
    from uav_downloader.subtitles import native_sherpa
    called = []
    monkeypatch.setattr(macos.multiprocessing, 'freeze_support', lambda: called.append('freeze'))
    monkeypatch.setattr(sys, 'argv', ['app', '--uav-native-worker', 'vad', '--help'])
    monkeypatch.setattr(native_sherpa, 'main', lambda args: called.append(args) or 0)
    assert macos.main() == 0
    assert called == ['freeze', ['vad', '--help']]
