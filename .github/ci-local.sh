#!/usr/bin/env bash
# Runs the checks of .github/workflows/build.yml locally, before pushing.
#
#   .github/ci-local.sh          tests + package install check (~1 min once cached)
#   .github/ci-local.sh --docker also builds the docker image for this machine
#
# The tests run in the "test" stage of the Dockerfile, so they see the same
# Python and requirements as the image. Docker caches that stage: it is only
# rebuilt when the requirements or the start of the Dockerfile change.
set -euo pipefail

cd "$(dirname "$0")/.."
image=cbpi-ci-base

echo "== requirements (Dockerfile target test)"
docker build -q --target test -t "$image" . >/dev/null

echo "== tests"
docker run --rm -v "$PWD":/cbpi-src:ro -w /tmp "$image" sh -c '
    set -e
    cp -r /cbpi-src /tmp/src && cd /tmp/src
    python -m pytest -q -p no:cacheprovider --disable-warnings tests
'

echo "== package installs and runs cbpi setup"
docker run --rm -v "$PWD":/cbpi-src:ro -w /tmp "$image" sh -c '
    set -e
    cp -r /cbpi-src /tmp/src && cd /tmp/src
    python setup.py -q sdist >/dev/null 2>&1
    PIP_NO_CACHE_DIR=1 pip install -q --no-deps dist/cbpi4-*.tar.gz
    mkdir /tmp/run && cd /tmp/run
    cbpi setup >/dev/null
    test -f config/config.json
'

if [[ ${1:-} == --docker ]]; then
    echo "== docker image (target deploy)"
    docker build -q --target deploy -t cbpi-ci-deploy . >/dev/null
fi

echo "OK"
