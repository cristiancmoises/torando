#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=lib/torando.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib/torando.sh"
torando_main disable "$@"
