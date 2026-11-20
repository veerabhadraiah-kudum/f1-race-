#!/usr/bin/env bash
# One-time asset fetch. Everything else installs from requirements.txt.
set -euo pipefail
cd "$(dirname "$0")"

echo "== fonts =="
mkdir -p assets/fonts assets/licenses
if [ ! -f assets/fonts/inter-400.woff2 ]; then
  node -e "
    const {execSync}=require('child_process');
    require('fs').mkdirSync('tools',{recursive:true});
    process.chdir('tools');
    if(!require('fs').existsSync('package.json')) execSync('npm init -y',{stdio:'ignore'});
    execSync('npm install --silent @fontsource/inter @fontsource/fraunces @fontsource/jetbrains-mono @fontsource/noto-sans-math mathjax-full',{stdio:'inherit'});
  "
  for w in 400 500 600 700; do cp tools/node_modules/@fontsource/inter/files/inter-latin-$w-normal.woff2 assets/fonts/inter-$w.woff2; done
  for w in 400 600 700; do cp tools/node_modules/@fontsource/fraunces/files/fraunces-latin-$w-normal.woff2 assets/fonts/fraunces-$w.woff2; done
  for w in 400 500 600; do cp tools/node_modules/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-$w-normal.woff2 assets/fonts/jetbrains-mono-$w.woff2; done
  cp tools/node_modules/@fontsource/noto-sans-math/files/noto-sans-math-latin-400-normal.woff2 assets/fonts/noto-sans-math-400.woff2
  cp tools/node_modules/@fontsource/*/LICENSE assets/licenses/ 2>/dev/null || true
else
  echo "   fonts already present"
fi

echo "== math typesetting cache =="
mkdir -p assets/math
python - <<'PY'
from engine import mathtex
mathtex.prebuild([
  r"a=\sigma\Big(\sum_{i} w_i x_i + b\Big)",
  r"\sigma(z)=\frac{1}{1+e^{-z}}",
  r"w_{t+1} = w_t - \eta\,\nabla L(w_t)",
  r"\min_{w}\,\frac{1}{n}\sum_{i=1}^{n}\ell\big(h(x_i;w),\,y_i\big)",
])
print("   equations cached in assets/math/cache.json")
PY

echo "done."
