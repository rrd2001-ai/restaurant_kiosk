#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../rasa_nlu"
rasa run --enable-api --interface 127.0.0.1 --port 5005 --model models
