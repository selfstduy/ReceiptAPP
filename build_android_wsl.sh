#!/bin/bash
# 在 WSL 下用「干净 PATH」执行 buildozer，避免 Windows 路径导致
# C compiler cannot create executables（freetype/libffi 等）

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 仅保留 Linux 常用路径 + 虚拟环境（若存在）
if [ -d "$HOME/buildozer-venv/bin" ]; then
  export PATH="$HOME/buildozer-venv/bin:/usr/bin:/bin:/usr/local/bin"
else
  export PATH="/usr/bin:/bin:/usr/local/bin:${HOME}/.local/bin"
fi

echo "Using PATH: $PATH"
echo "Building in: $SCRIPT_DIR"
buildozer -v android debug
