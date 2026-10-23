"""Supervised macOS ASR/VAD worker; stdout is reserved for machine results."""
from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx


def read_audio(path):
    with wave.open(str(path), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(),
                source.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('Expected mono PCM16 at 16 kHz')
        if source.getnframes() > 29 * 16000:
            raise ValueError('Recognition window is too long')
        return np.frombuffer(source.readframes(source.getnframes()),
                             dtype='<i2').astype(np.float32) / 32768.0


def detect(args):
    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = args.vad_model
    config.silero_vad.threshold = args.threshold
    config.silero_vad.min_speech_duration = args.minimum_speech
    config.silero_vad.max_speech_duration = args.maximum_speech
    config.silero_vad.min_silence_duration = 0.3
    config.sample_rate = 16000
    config.num_threads = args.threads
    detector = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)
    segments = []

    def drain():
        while not detector.empty():
            segment = detector.front
            segments.append((segment.start / 16000,
                             (segment.start + len(segment.samples)) / 16000))
            detector.pop()
            if len(segments) > 20_000:
                raise ValueError('Too many speech segments')

    with wave.open(args.file, 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(),
                source.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('Expected mono PCM16 at 16 kHz')
        while chunk := source.readframes(512):
            samples = np.frombuffer(chunk, dtype='<i2').astype(np.float32) / 32768.0
            if len(samples) < 512:
                samples = np.pad(samples, (0, 512 - len(samples)))
            detector.accept_waveform(samples)
            drain()
    detector.flush()
    drain()
    print(f'Detected {len(segments)} speech segments:')
    for index, (start, end) in enumerate(segments):
        # The existing VAD parser consumes centiseconds from whisper.cpp.
        print(f'Speech segment {index}: start = {start * 100:.2f}, end = {end * 100:.2f}')


def transcribe(args):
    root = Path(args.model_dir)
    common = dict(tokens=str(root / 'tokens.txt'), num_threads=args.threads,
                  provider='cpu', decoding_method='greedy_search')
    if args.engine == 'parakeet':
        recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=str(root / 'model.int8.onnx'), **common)
    else:
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(root / 'encoder-epoch-99-avg-1.int8.onnx'),
            decoder=str(root / 'decoder-epoch-99-avg-1.onnx'),
            joiner=str(root / 'joiner-epoch-99-avg-1.int8.onnx'), **common)
    # Keep memory bounded and emit each result promptly for the parent's watchdog.
    for path in args.files:
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, read_audio(path))
        recognizer.decode_stream(stream)
        print(stream.result, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    vad = modes.add_parser('vad')
    vad.add_argument('--file', required=True)
    vad.add_argument('--vad-model', required=True)
    vad.add_argument('--threshold', type=float, required=True)
    vad.add_argument('--minimum-speech', type=float, required=True)
    vad.add_argument('--maximum-speech', type=float, required=True)
    vad.add_argument('--threads', type=int, required=True)
    asr = modes.add_parser('asr')
    asr.add_argument('--model-dir', required=True)
    asr.add_argument('--engine', choices=('parakeet', 'reazonspeech'), required=True)
    asr.add_argument('--threads', type=int, required=True)
    asr.add_argument('files', nargs='+')
    args = parser.parse_args(argv)
    if args.mode == 'vad':
        detect(args)
    else:
        transcribe(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
