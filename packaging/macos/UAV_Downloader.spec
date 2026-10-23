# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import platform
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
stage = root / 'build' / 'macos-assets'
datas = [
    (str(stage / 'components'), 'components'),
    (str(stage / 'native-licenses'), 'third_party_licenses/native'),
    (str(stage / 'homebrew-components.json'), 'third_party_licenses'),
    (str(root / 'LICENSE'), '.'),
    (str(root / 'THIRD_PARTY_NOTICES.md'), '.'),
    (str(root / 'third_party_licenses'), 'third_party_licenses'),
]
binaries = [
    ((stage / 'mpv-path.txt').read_text().strip(), 'player'),
    (str(stage / 'ffmpeg'), '.'),
]
hiddenimports = ['uav_downloader.subtitles.native_sherpa',
                 'uav_downloader.core.macos_check', 'socks', 'urllib3.contrib.socks']
for package in ('cloudscraper', 'certifi', 'customtkinter', 'curl_cffi',
                'ctranslate2', 'sentencepiece', 'opencc', 'sherpa_onnx'):
    package_data, package_bins, package_imports = collect_all(package)
    datas += package_data
    binaries += package_bins
    hiddenimports += package_imports
for package in ('numpy', 'PyYAML', 'sherpa-onnx', 'sherpa-onnx-core'):
    datas += copy_metadata(package)

a = Analysis(
    [str(root / 'src/uav_downloader/entrypoints/macos.py')],
    pathex=[str(root / 'src')], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, excludes=['pytest', 'PyInstaller'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='UAV Downloader',
    console=False, argv_emulation=False, strip=False, upx=False,
    target_arch='arm64', codesign_identity=None,
)
collected = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
                    name='UAV Downloader')
app = BUNDLE(
    collected, name='UAV Downloader.app',
    bundle_identifier='local.uav-downloader.browser', version='3.3.0',
    info_plist={
        'CFBundleDisplayName': 'UAV Downloader',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': platform.mac_ver()[0],
        'NSLocalNetworkUsageDescription': 'Connect to local proxies or video sources you choose.',
    },
)
