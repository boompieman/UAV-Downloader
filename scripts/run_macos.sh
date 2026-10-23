#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'This launcher requires macOS.' >&2
    exit 1
fi
if ! command -v uv >/dev/null; then
    echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi
case "${1:-browser}" in
    browser) command_name=uav-browser ;;
    watcher) command_name=uav-watcher ;;
    player) command_name=uav-player ;;
    *) echo 'Choose browser, watcher or player.' >&2; exit 1 ;;
esac
if [[ $# -gt 0 ]]; then shift; fi
exec uv run --python 3.12 --extra macos "$command_name" "$@"
