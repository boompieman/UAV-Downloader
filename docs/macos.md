# macOS: download, recognize Japanese, and play local videos

The standalone `UAV Downloader.app` includes Python, Tk, ffmpeg, native speech
and translation runtimes, verified subtitle models, and mpv with its native
libraries. Open the app directly; uv, Homebrew and the source checkout are not
needed at runtime. Downloads default to `~/Downloads/UAV Downloader` unless
you have already selected another folder. In Settings, choose your AI subtitle
language and Auto or Parakeet recognition. The Download tab provides Play and
Open local videos.

The current local build targets Apple Silicon and macOS 26.5 or newer. It is
ad-hoc signed, without Developer ID signing or Apple notarization. The app is
about 1.2 GB because its Japanese and translation models are included and can
run offline. External video-site access still requires a working connection
and whatever access the source website requires.

## Build the standalone app

On the build Mac, install uv and mpv, then run from the repository:

```sh
uv sync --extra macos --extra macos-build
uv run --no-sync python scripts/build_macos_app.py
```

The result is `dist/macos/UAV Downloader.app`. The build verifies and bundles
both Japanese recognition models and local translation models. To reuse an
existing `subtitle_tools` cache, pass `--component-cache /path/to/cache`.
Every model still passes its size, hash or complete manifest verification.
The build gathers mpv's dependent libraries through PyInstaller, relocates
their load paths, and includes native component metadata and license texts.

For a frozen acceptance check, invoke the app executable with
`--uav-bundle-check /path/to/Japanese-test.mp4 /path/to/report.json`.
This checks real local HLS download/merge, both ASR engines, all three subtitle
languages, Tk startup, bundled mpv hardware decoding, pause/seek and subtitle
selection. It prohibits model downloads and leaves test media in temporary
storage. Use a test clip with Japanese speech and an H.264 video stream.

## Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[mpv](https://mpv.io/installation/). With Homebrew available:

```sh
brew install uv mpv
uv python install 3.12
uv sync --extra macos
```

Run the last two commands from this repository. Python and project packages
are managed by uv; Homebrew supplies the external mpv player.

Double-click `UAV Browser.command` or `UAV Watcher.command` in this checkout.
The launchers locate uv, synchronize the macOS extra and run the application.
You can also run `uv run --extra macos uav-browser` or
`uv run --extra macos uav-watcher` in Terminal.
These `.command` files are the source launchers; the packaged `.app` above
does not use them.

## Japanese recognition

In Settings → Recognition quality, choose Auto (ReazonSpeech, about 186 MB)
or Parakeet (Japanese, about 656 MB). Source installations download models on
first use; the standalone app carries them inside the bundle. Both paths use
fixed source identities, sizes and SHA-256 checks. In macOS, Parakeet uses
NVIDIA's Japanese model through its INT8 CTC ONNX conversion and does not
download the Windows runtime. Auto reuses the existing verified ReazonSpeech
pack for its model files; its Windows binaries are unused.

The native Silero ONNX speech detector runs in a supervised subprocess.
Recognition reuses the existing bounded audio windows and absolute subtitle
timeline. Cancellation and timeouts stop native workers. Invalid Parakeet
output or recognition-process failure falls back to native ReazonSpeech.
Integrity and storage errors stop the job. Whisper quality presets remain
Windows-only and are hidden in the Mac selector.

Select Japanese, English, Traditional Chinese, or all three under AI subtitles.
Use “Subtitle Local Files” for videos already downloaded. The existing local
translation models work on macOS; optional LLM translation settings also remain
available. Audio and video stay local.

## UAV Player, powered by mpv

This project integrates the upstream [mpv](https://github.com/mpv-player/mpv)
player as an independent playback window. It uses mpv's decoder and controls.
The standalone app includes mpv; source installations use a separate mpv
installation. No player binaries are checked into this repository.

- In Browser's Download tab, click **Play** on a completed video.
- Click **Open local videos** to choose existing files, including older downloads.
- Double-click `UAV Player.command` to open the file picker independently.
- From Terminal: `uv run uav-player "/path/to/video.mp4"`. Multiple paths form
  a playlist.

Playback requests `hwdec=auto`; supported Mac codecs use VideoToolbox and
otherwise fall back to software decoding. mpv automatically loads matching
`.ja.srt`, `.en.srt`, and `.zh-TW.srt` files beside the video, preferring
Traditional Chinese, Chinese, Japanese, then English. The files must already
exist when playback starts; reopen the video after generating new subtitles.

Space pauses/resumes, Left/Right seeks, `f` toggles full screen, `j` cycles
subtitle tracks and `v` toggles subtitle visibility. The mouse reveals mpv's
playback controls. See the [mpv manual](https://mpv.io/manual/stable/).

The integration starts mpv with a clean configuration and no playback-history
writes. It accepts existing local video files only. File-picker cancellation
starts no player; launch and decoding failures are reported in Browser.
