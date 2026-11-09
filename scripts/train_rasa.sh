#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../rasa_nlu"
rasa train nlu --config config.yml --nlu data/nlu.yml --out models
