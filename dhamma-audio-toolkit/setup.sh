#!/usr/bin/env bash
# Restores the working environment for the Dhamma talk audio/video pipeline.
# Takes about 5 minutes on a fresh container.
set -euo pipefail
cd "$(dirname "$0")"

echo "== system packages =="
apt-get update -qq
apt-get install -y ffmpeg unzip

echo "== python packages =="
python3 -m pip install -q --break-system-packages \
    numpy soundfile sherpa-onnx pillow opencv-python-headless

echo "== speech models =="
# NOTE: huggingface.co is blocked by the agent egress policy in this environment.
# These GitHub release mirrors are reachable and carry the same models.
mkdir -p models && cd models
if [ ! -d sherpa-onnx-whisper-base.en ]; then
  curl -sSL -o whisper.tar.bz2 \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-base.en.tar.bz2"
  tar xjf whisper.tar.bz2 && rm whisper.tar.bz2
fi
[ -f silero_vad.onnx ] || curl -sSL -o silero_vad.onnx \
  "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"

echo
echo "Ready. Next: python3 01_analyze.py <talk.mp3>"
