#!/usr/bin/env bash
# Automated QA across every scene: glyph coverage + title-safe bounds.
set -uo pipefail
cd "$(dirname "$0")/.."
VENV=${VENV:-.venv}
fail=0
for spec in \
  "scenes.s1_gradient_descent:GradientDescent" \
  "scenes.s2_neural_network:NeuralNetwork" \
  "scenes.s3_neuron:SingleNeuron" \
  "scenes.s4_equations:EquationsAndTerms"
do
  echo "=== $spec"
  ${VENV}/bin/python -m engine.qa "$spec" || fail=1
done
exit $fail
