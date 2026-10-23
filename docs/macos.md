# macOS: download, recognize Japanese, and play local videos

The source version runs on macOS with a uv-managed Python 3.12. It uses the
existing Browser and Watcher interfaces. No Windows executable is needed.

## Setup

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
These are source launchers; this change does not create a signed, notarized,
self-contained macOS application distribution.

## Japanese recognition

In Settings → Recognition quality, choose Auto (ReazonSpeech, about 186 MB)
or Parakeet (Japanese, about 656 MB). Models are downloaded on first use with
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
mpv is installed separately; no player binaries are copied into this repository.

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
