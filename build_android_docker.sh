#!/bin/bash
# 使用官方 kivy/buildozer Docker 镜像构建 APK，用于规避 WSL 下 freetype
# 「C compiler cannot create executables」问题。
# 需已安装 Docker（Docker Desktop 或 Linux 下 docker-engine）。

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CACHE_DIR="${BUILDozER_CACHE:-$HOME/.buildozer}"
mkdir -p "$CACHE_DIR"

echo "Project: $SCRIPT_DIR"
echo "Cache:   $CACHE_DIR"
echo "Running: kivy/buildozer -v android debug"
docker run --interactive --tty --rm \
  --volume "$CACHE_DIR":/home/user/.buildozer \
  --volume "$SCRIPT_DIR":/home/user/hostcwd \
  --workdir /home/user/hostcwd \
  kivy/buildozer -v android debug
