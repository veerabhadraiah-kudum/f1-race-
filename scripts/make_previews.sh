#!/usr/bin/env bash
# Per-scene previews + contact sheets.
# Every scene is rendered independently — that is the review loop for this film.
set -euo pipefail
cd "$(dirname "$0")/.."
VENV=${VENV:-.venv}
PY=$VENV/bin/python

SCENES=(
  "scenes.s1_gradient_descent:GradientDescent"
  "scenes.s2_neural_network:NeuralNetwork"
  "scenes.s3_neuron:SingleNeuron"
  "scenes.s4_equations:EquationsAndTerms"
)

for spec in "${SCENES[@]}"; do
  echo "== $spec"
  $PY build.py scene   "$spec"                 # 1080p scene master
  $PY build.py sheet   "$spec" 9               # 9-frame contact sheet
  $PY build.py preview "$spec" 4 --scale 0.5   # 4 s half-res motion preview
done
