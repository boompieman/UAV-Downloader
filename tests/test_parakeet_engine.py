import hashlib
import wave
from pathlib import Path

import pytest

from uav_downloader.core import config
from uav_downloader.subtitles import engine as subtitles


def _payload():
    return {
        'lang': '', 'emotion': '', 'event': '',
        'text': '日本語です。',
        'tokens': [' ', '日本', '語', 'です', '。'],
        'timestamps': [0.0, 0.3, 0.6, 0.9, 1.2],
        'durations': [], 'ys_log_probs': [], 'words': [],
    }


@pytest.fixture
def model(monkeypatch, tmp_path):
    monkeypatch.setattr(subtitles, '_cache_root', lambda: str(tmp_path))
    files = {'model.int8.onnx': b'model', 'tokens.txt': b'tokens'}
    monkeypatch.setattr(subtitles, 'PARAKEET_MODEL_FILES', {
        name: (len(data), hashlib.sha256(data).hexdigest())
        for name, data in files.items()
    })
    return files


def test_parakeet_downloads_pinned_files_and_rejects_corruption(
        monkeypatch, model):
    downloads = []

    def download(url, path, size, sha256, *_args):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(model[target.name])
        downloads.append((url, size, sha256))

    monkeypatch.setattr(subtitles, '_download_verified', download)
    root = subtitles._prepare_parakeet_model(None, None)
    assert len(downloads) == 2
    assert all(subtitles.PARAKEET_MODEL_REVISION in url
               for url, *_rest in downloads)
    assert subtitles._verify_parakeet_model(root, None) == root
    with open(root + '/tokens.txt', 'wb') as output:
        output.write(b'broken')
    with pytest.raises(subtitles.SubtitleError, match='integrity'):
        subtitles._verify_parakeet_model(root, None)


def test_parakeet_download_respects_cancellation(model):
    with pytest.raises(subtitles.SubtitleCancelled):
        subtitles._prepare_parakeet_model(None, lambda: True)


def test_parakeet_rejects_symlinked_model_directory(model, tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(subtitles.SubtitleError, match='integrity'):
        subtitles._verify_parakeet_model(str(link), None)
    assert not list(target.iterdir())


def test_runtime_prepares_parakeet_only_when_selected(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(subtitles, '_cache_root', lambda: str(tmp_path))
    monkeypatch.setattr(subtitles, '_verify_whisper_install',
                        lambda *_args, **_kwargs: 'whisper.exe')
    monkeypatch.setattr(subtitles, '_prepare_reazonspeech_runtime',
                        lambda *_args: 'shared-pack')
    monkeypatch.setattr(subtitles, '_prepare_parakeet_model',
                        lambda *_args: calls.append('parakeet'))
    monkeypatch.setattr(subtitles, '_download_verified', lambda *_args: None)
    for selection in ('auto', 'parakeet', 'fast'):
        with subtitles._recognition_profile_scope(
                subtitles.recognition_profile(selection)):
            _exe, model, _vad = subtitles._prepare_runtime_locked(None, None)
        if selection in ('auto', 'parakeet'):
            assert model == 'shared-pack'
    assert calls == ['parakeet']


def test_parakeet_cli_selects_cpu_ctc_without_transducer_models(tmp_path):
    args = subtitles._reazonspeech_cli_args(
        str(tmp_path), ['island-00000.wav'], ctc_model_dir=str(tmp_path / 'ja'))
    assert '--nemo-ctc-model=' + str(tmp_path / 'ja/model.int8.onnx') in args
    assert '--tokens=' + str(tmp_path / 'ja/tokens.txt') in args
    assert '--provider=cpu' in args
    assert not any(arg.startswith(('--encoder=', '--decoder=', '--joiner='))
                   for arg in args)
    with pytest.raises(subtitles.SubtitleError, match='unsafe'):
        subtitles._reazonspeech_cli_args(
            str(tmp_path), ['../audio.wav'], ctc_model_dir=str(tmp_path / 'ja'))


@pytest.mark.parametrize('tokens', [
    [' ', '日本', '語', 'です', '。'],
    [' 日本', '語', 'です', '。'],
    ['日本', '語', 'です', '。'],
])
def test_ctc_parser_preserves_text_and_absolute_timing(tokens):
    payload = _payload()
    payload['tokens'] = tokens
    payload['timestamps'] = [round(i * 0.3, 2) for i in range(len(tokens))]
    cues = subtitles._parse_reazonspeech_payload(
        payload, subtitles.SpeechIsland(30, 32), 2, ctc=True)
    assert ''.join(cue.text for cue in cues) == '日本語です。'
    assert all(30 <= cue.start < cue.end <= 32 for cue in cues)
    assert cues[0].start == (30.3 if tokens[0] == ' ' else 30)
    with pytest.raises(subtitles.ReazonSpeechStructuralError):
        subtitles._parse_reazonspeech_payload(
            payload, subtitles.SpeechIsland(30, 32), 2)


@pytest.mark.parametrize('field,value', [
    ('text', '違う文章'), ('timestamps', [0, 0.3, float('nan'), 1, 2]),
    ('timestamps', [0, 0.3]), ('ys_log_probs', [0]),
    ('tokens', ['\x00', '日本', '語', 'です', '。']),
])
def test_ctc_parser_still_rejects_invalid_output(field, value):
    payload = _payload()
    payload[field] = value
    with pytest.raises(subtitles.ReazonSpeechStructuralError):
        subtitles._parse_reazonspeech_payload(
            payload, subtitles.SpeechIsland(30, 32), 2, ctc=True)


@pytest.mark.parametrize('failure', [None, 'invalid', 'cancel', 'storage'])
def test_parakeet_pipeline_reports_engine_and_only_falls_back_for_invalid_output(
        monkeypatch, tmp_path, failure):
    wav = tmp_path / 'audio.wav'
    with wave.open(str(wav), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b'\0\0' * 64_000)
    whisper = tmp_path / 'whisper-cli.exe'
    whisper.touch()
    (tmp_path / 'whisper-vad-speech-segments.exe').touch()
    monkeypatch.setattr(subtitles, '_verify_parakeet_model',
                        lambda *_args: 'parakeet-model')
    monkeypatch.setattr(subtitles, '_verify_reazonspeech_install',
                        lambda root, **_kwargs: root)
    monkeypatch.setattr(subtitles, '_run_external_vad',
                        lambda *_args, **_kwargs: [subtitles.SpeechIsland(1, 3)])

    def batch(*_args, **kwargs):
        assert kwargs['ctc_model_dir'] == 'parakeet-model'
        if failure == 'cancel':
            raise subtitles.SubtitleCancelled('cancelled')
        if failure == 'storage':
            raise subtitles.SubtitleStorageError('disk full')
        return [{}] if failure == 'invalid' else [_payload()]

    monkeypatch.setattr(subtitles, '_run_reazonspeech_cli_batch', batch)
    fallback_calls = []
    monkeypatch.setattr(subtitles, '_prepare_whisper_fallback_model',
                        lambda *_args: fallback_calls.append(True) or 'small.bin')
    monkeypatch.setattr(subtitles, '_run_whisper',
                        lambda *_args, **_kwargs: 'fallback.srt')
    outcomes = []

    def run():
        return subtitles._run_recognition(
            subtitles.recognition_profile('parakeet'), str(whisper), 'pack',
            'vad', str(wav), str(tmp_path / 'out'), 'log', None,
            outcome_callback=lambda p, f: outcomes.append((p.engine, f)))

    if failure in ('cancel', 'storage'):
        with pytest.raises(subtitles.SubtitleError):
            run()
        assert not fallback_calls
        assert not outcomes
    else:
        result = run()
        if failure:
            assert result == 'fallback.srt'
            assert fallback_calls == [True]
            assert outcomes == [('whisper', True)]
        else:
            assert subtitles.parse_srt(Path(result).read_text(encoding='utf-8'))[0].text
            assert not fallback_calls
            assert outcomes == [('parakeet', False)]


def test_parakeet_preference_and_provenance_include_token_identity(monkeypatch):
    assert config._normalize_recognition_quality(' PARAKEET ') == 'parakeet'
    profile = subtitles.recognition_profile('parakeet')
    assert profile.engine == 'parakeet'
    signature = subtitles._asr_signature(profile)
    assert signature != subtitles._asr_signature(subtitles.recognition_profile('auto'))
    monkeypatch.setitem(subtitles.PARAKEET_MODEL_FILES, 'tokens.txt', (1, 'a' * 64))
    assert signature != subtitles._asr_signature(profile)
