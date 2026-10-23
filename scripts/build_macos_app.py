#!/usr/bin/env python3
"""Build a self-contained Apple Silicon app with verified local subtitle models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from uav_downloader.subtitles import engine
from uav_downloader.ui.player import find_mpv


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-cache', type=Path,
                        help='Reuse a subtitle_tools cache; all files are verified')
    args = parser.parse_args(argv)
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('Build this app on an Apple Silicon Mac')
    if args.component_cache:
        cache = str(args.component_cache.resolve())
        engine._cache_root = lambda: cache
    stage = ROOT / 'build' / 'macos-assets'
    stage.mkdir(parents=True, exist_ok=True)
    components = stage / 'components'
    components.mkdir(exist_ok=True)
    print('Preparing verified speech and translation models', flush=True)
    parakeet = engine._prepare_parakeet_model(None, None)
    reazon = engine._prepare_reazonspeech_runtime(None, None)
    translation = engine._prepare_translation_runtime(None, None)
    translation_root = Path(translation['ja-en']).parents[1]
    for source, name in (
            (parakeet, f'parakeet-ja-{engine.PARAKEET_MODEL_REVISION}'),
            (reazon, Path(engine.REAZONSPEECH_PACK_NAME).stem),
            (translation_root, Path(engine.TRANSLATION_PACK_NAME).stem)):
        target = components / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    engine._download_verified(
        engine.NATIVE_VAD_URL, str(components / 'silero-vad.onnx'),
        engine.NATIVE_VAD_SIZE, engine.NATIVE_VAD_SHA256, 'model', None, None)
    import imageio_ffmpeg
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), stage / 'ffmpeg')
    mpv = Path(find_mpv()).resolve()
    (stage / 'mpv-path.txt').write_text(str(mpv), encoding='utf-8')
    # Preserve source locations, versions and license texts for bundled Homebrew libraries.
    dependencies = subprocess.check_output(['brew', 'deps', 'mpv'], text=True).splitlines()
    manifest = json.loads(subprocess.check_output(
        ['brew', 'info', '--json=v2', 'mpv', *dependencies], text=True))
    (stage / 'homebrew-components.json').write_text(
        json.dumps(manifest, indent=2), encoding='utf-8')
    notices = stage / 'native-licenses'
    notices.mkdir(exist_ok=True)
    for formula in manifest['formulae']:
        prefix = Path(subprocess.check_output(
            ['brew', '--prefix', formula['name']], text=True).strip())
        for path in prefix.iterdir():
            if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                target = notices / formula['name']
                target.mkdir(exist_ok=True)
                shutil.copy2(path, target / path.name)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm',
        '--distpath', str(ROOT / 'dist' / 'macos'),
        '--workpath', str(ROOT / 'build' / 'pyinstaller-macos'),
        str(ROOT / 'packaging' / 'macos' / 'UAV_Downloader.spec'),
    ], cwd=ROOT, check=True)
    print(ROOT / 'dist' / 'macos' / 'UAV Downloader.app', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
