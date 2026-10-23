import sys
import wave

import pytest

from uav_downloader.subtitles import engine


def test_native_parakeet_preparation_never_installs_windows_runtime(monkeypatch, tmp_path):
    pytest.importorskip('sherpa_onnx')
    monkeypatch.setattr(engine, '_cache_root', lambda: str(tmp_path))
    monkeypatch.setattr(engine, 'recognition_profile', lambda: engine.RECOGNITION_PROFILES['parakeet'])
    monkeypatch.setattr(engine, '_prepare_parakeet_model', lambda *_args: 'native-model')
    monkeypatch.setattr(engine, '_prepare_reazonspeech_runtime',
                        lambda *_args: pytest.fail('No Windows pack needed for native Parakeet'))
    downloads = []

    def download(url, path, size, sha256, *_args):
        downloads.append((url, size, sha256))
        return path

    monkeypatch.setattr(engine, '_download_verified', download)
    exe, model, vad = engine._prepare_native_runtime(None, None)
    assert (exe, model) == (sys.executable, 'native-model')
    assert vad.endswith('.onnx')
    assert downloads == [(engine.NATIVE_VAD_URL, engine.NATIVE_VAD_SIZE, engine.NATIVE_VAD_SHA256)]


def test_native_batch_uses_python_and_pinned_ctc_model():
    args = engine._reazonspeech_cli_args(
        'unused', ['island-00000.wav'], ctc_model_dir='/models/ja', native=True)
    assert args[:3] == [sys.executable, engine.NATIVE_SHERPA_WORKER, 'asr']
    assert args[args.index('--engine') + 1] == 'parakeet'
    assert args[args.index('--model-dir') + 1] == '/models/ja'
    assert not any(arg.endswith('.exe') for arg in args)


def test_native_provenance_distinguishes_vad_and_fallback(monkeypatch):
    monkeypatch.setattr(engine.sys, 'platform', 'darwin')
    captured = []
    original = engine._stable_signature
    monkeypatch.setattr(engine, '_stable_signature',
                        lambda identity: captured.append(identity) or original(identity))
    engine._asr_signature(engine.RECOGNITION_PROFILES['parakeet'])
    identity = captured[-1]
    assert identity['vad']['model_sha256'] == engine.NATIVE_VAD_SHA256
    assert identity['structural_fallback']['engine'] == 'reazonspeech'
    assert captured[0]['structural_fallback'] is None


def test_worker_rejects_non_pcm_or_oversized_recognition_windows(tmp_path):
    pytest.importorskip('sherpa_onnx')
    from uav_downloader.subtitles.native_sherpa import read_audio
    path = tmp_path / 'audio.wav'
    for channels, seconds in ((2, 1), (1, 30)):
        with wave.open(str(path), 'wb') as output:
            output.setnchannels(channels)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b'\0\0' * channels * 16000 * seconds)
        with pytest.raises(ValueError):
            read_audio(path)


@pytest.mark.parametrize('kind', ['cancel', 'storage', 'invalid'])
def test_native_parakeet_failure_uses_reazon_only_for_invalid_output(monkeypatch, tmp_path, kind):
    path = tmp_path / 'audio.wav'
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b'\0\0' * 32000)
    monkeypatch.setattr(engine, '_verify_parakeet_model', lambda path, *_args: path)
    monkeypatch.setattr(engine, '_verify_reazonspeech_install', lambda path, **_kwargs: path)
    monkeypatch.setattr(engine, '_run_external_vad',
                        lambda *_args, **_kwargs: [engine.SpeechIsland(0, 2)])
    calls = []

    def batch(*_args, **kwargs):
        assert kwargs['native']
        if kind == 'cancel':
            raise engine.SubtitleCancelled()
        if kind == 'storage':
            raise engine.SubtitleStorageError('disk')
        if not calls:
            calls.append('parakeet')
            return [{}]
        return [{'lang': '', 'emotion': '', 'event': '', 'text': '日本語',
                 'tokens': ['日本', '語'], 'timestamps': [0.1, 0.6],
                 'durations': [], 'ys_log_probs': [-0.1, -0.1], 'words': []}]

    monkeypatch.setattr(engine, '_run_reazonspeech_cli_batch', batch)
    monkeypatch.setattr(engine, '_prepare_reazonspeech_runtime',
                        lambda *_args: calls.append('reazon') or 'pack')
    monkeypatch.setattr(engine, '_prepare_whisper_fallback_model',
                        lambda *_args: pytest.fail('No Windows fallback'))
    outcomes = []

    def run():
        return engine._run_recognition(
            engine.RECOGNITION_PROFILES['parakeet'], sys.executable,
            'model', 'vad.onnx', str(path), str(tmp_path / 'out'), 'log', None,
            outcome_callback=lambda p, f: outcomes.append((p.engine, f)))

    if kind == 'invalid':
        assert run().endswith('.srt')
        assert calls == ['parakeet', 'reazon']
        assert outcomes == [('reazonspeech', True)]
    else:
        with pytest.raises(engine.SubtitleError):
            run()
        assert not calls
