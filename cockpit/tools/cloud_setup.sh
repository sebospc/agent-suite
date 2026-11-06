#!/usr/bin/env bash
# SessionStart hook: cloud sessions get the same rtk the Mac has. The Mac installs rtk with brew, so this exits there.
# Pinned version and checksum, so a new upstream release never changes what runs; any failure lets the session start.
set -uo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
command -v rtk >/dev/null && exit 0

version="0.43.0"
asset="rtk-x86_64-unknown-linux-musl.tar.gz"
expected_sha256="ff8a1e7766496e175291a85aeca1dc97c9ff6df33e51e5893d1fbc78fea2a609"
bin_dir="$HOME/.local/bin"
download_dir="$(mktemp -d)"

if curl -fsSL -o "$download_dir/$asset" "https://github.com/rtk-ai/rtk/releases/download/v$version/$asset" \
  && echo "$expected_sha256  $download_dir/$asset" | sha256sum -c --status \
  && mkdir -p "$bin_dir" && tar -xzf "$download_dir/$asset" -C "$bin_dir" rtk; then
  [ -n "${CLAUDE_ENV_FILE:-}" ] && echo "export PATH=\"$bin_dir:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  echo "cloud_setup: rtk $version installed"
else
  echo "cloud_setup: rtk $version not installed; commands run without it"
fi
rm -rf "${download_dir:?}"
exit 0
