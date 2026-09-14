#!/usr/bin/env bash
#
# Run the blocking .github/workflows/ci.yml jobs locally, in the same order
# and with the same commands, so a PR isn't the first place you find out.
#
# Usage, from the repository root:
#
#   ./scripts/ci-local.sh            # every blocking job
#   ./scripts/ci-local.sh py         # ruff + black + pytest + python half of build
#   ./scripts/ci-local.sh ts         # eslint + prettier + vitest + next build
#   ./scripts/ci-local.sh --install  # install requirements-dev.txt first
#   ./scripts/ci-local.sh --all      # also run the non-blocking jobs (mypy, audit)
#
# Windows: run this in Git Bash, not PowerShell or cmd — it uses the same
# bash and `git ls-files` guards the workflow does.
#
# Python tools are invoked as `python -m ruff` rather than bare `ruff`, so
# this works whether or not pip's Scripts directory is on PATH — on Windows
# it usually isn't, and pip says so in a warning that's easy to scroll past.
# Set PERFPILOT_PYTHON to force a specific interpreter:
#
#   PERFPILOT_PYTHON="py -3.11" ./scripts/ci-local.sh py
#
# This is a convenience wrapper, not a replacement for CI. It runs on your
# machine, not ubuntu-latest, so it can still disagree on Node version and
# line endings. For a faithful run use `act` — see
# docs/development/local-development.md#checking-ci-before-you-push.
#
# NOT part of issue #10. Delete it or land it as its own small PR.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

SCOPE="${1:-all-blocking}"
RUN_INSTALL=false
RUN_NONBLOCKING=false
for arg in "$@"; do
  case "$arg" in
    --install) RUN_INSTALL=true ;;
    --all) RUN_NONBLOCKING=true ;;
  esac
done
case "$SCOPE" in
  --install | --all) SCOPE="all-blocking" ;;
esac

RESULTS=()
FAILED=0
# Set once `pnpm install` succeeds. Everything JS downstream reads this, so a
# failed install reports one clear failure instead of four confusing ones.
PNPM_READY=false
PY=()

if [ -t 1 ]; then
  R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; B=$'\033[1m'; N=$'\033[0m'
else
  R=""; G=""; Y=""; B=""; N=""
fi

run_job() {
  local name="$1"; shift
  printf '\n%s=== %s ===%s\n' "$B" "$name" "$N"
  if "$@"; then
    RESULTS+=("${G}PASS${N}  $name")
  else
    RESULTS+=("${R}FAIL${N}  $name")
    FAILED=1
  fi
}

skip_job() {
  RESULTS+=("${Y}SKIP${N}  $1 — $2")
  printf '\n%s=== %s ===%s\n%s\n' "$B" "$1" "$N" "$2"
}

want() { [ "$SCOPE" = "all-blocking" ] || [ "$SCOPE" = "$1" ]; }

# --------------------------------------------------------------------------
# Find an interpreter that actually runs.
#
# On Windows, bare `python` is usually the Microsoft Store alias stub, which
# prints "Python was not found..." and exits non-zero instead of running
# anything — so candidates are probed by executing code, not by `command -v`.
# 3.11 is tried first because that's what CI pins.
# --------------------------------------------------------------------------
find_python() {
  local candidates=()
  if [ -n "${PERFPILOT_PYTHON:-}" ]; then
    # shellcheck disable=SC2206  # deliberate word-splitting: "py -3.11"
    local override=($PERFPILOT_PYTHON)
    candidates+=("${override[*]}")
  fi
  candidates+=("py -3.11" "python3.11" "python3" "python" "py -3" "py")

  local c parts
  for c in "${candidates[@]}"; do
    # shellcheck disable=SC2206  # deliberate word-splitting on the candidate
    parts=($c)
    if "${parts[@]}" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
      PY=("${parts[@]}")
      return 0
    fi
  done
  return 1
}

py_has_module() { "${PY[@]}" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('$1') else 1)" >/dev/null 2>&1; }

# --------------------------------------------------------------------------
# Guards, mirroring the workflow's own `git ls-files` checks.
# --------------------------------------------------------------------------
has_ts=$(git ls-files ':(glob)apps/web/**/*.ts' ':(glob)apps/web/**/*.tsx' \
  ':(glob)packages/schemas/typescript/**/*.ts')
has_tscss=$(git ls-files ':(glob)apps/web/**/*.ts' ':(glob)apps/web/**/*.tsx' \
  ':(glob)apps/web/**/*.css' ':(glob)packages/schemas/typescript/**/*.ts')
has_webtests=$(git ls-files ':(glob)apps/web/**/*.test.ts' ':(glob)apps/web/**/*.test.tsx')

# --------------------------------------------------------------------------
# Python jobs
# --------------------------------------------------------------------------
if want py; then
  if ! find_python; then
    printf '%sNo working Python found.%s\n\n' "$R" "$N"
    printf 'Tried: py -3.11, python3.11, python3, python, py -3, py\n\n'
    printf 'On Windows this usually means the Microsoft Store alias is shadowing\n'
    printf 'a real install. Either turn it off (Settings > Apps > Advanced app\n'
    printf 'settings > App execution aliases > python.exe / python3.exe), or point\n'
    printf 'this script at your interpreter directly:\n\n'
    printf '  PERFPILOT_PYTHON="py -3.11" ./scripts/ci-local.sh py\n\n'
    printf 'A virtualenv is the tidiest fix, and matches what CI installs:\n\n'
    printf '  py -3.11 -m venv .venv && source .venv/Scripts/activate\n'
    printf '  pip install -r requirements-dev.txt\n\n'
    exit 1
  fi

  pyver=$("${PY[@]}" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
  printf '%spython:%s %s (%s)\n' "$B" "$N" "${PY[*]}" "$pyver"
  if [ "$pyver" != "3.11" ]; then
    printf '%snote:%s CI pins Python 3.11 and pyproject.toml targets py311. You are on\n' "$Y" "$N"
    printf '      %s, so this run can disagree with CI. Usually fine for ruff/black\n' "$pyver"
    printf '      (their target-version is set explicitly); less so for pytest.\n'
  fi

  if $RUN_INSTALL; then
    printf '\n%s=== pip install -r requirements-dev.txt ===%s\n' "$B" "$N"
    "${PY[@]}" -m pip install -r requirements-dev.txt || exit 1
  fi

  missing=()
  for m in ruff black pytest; do py_has_module "$m" || missing+=("$m"); done
  if [ ${#missing[@]} -gt 0 ]; then
    printf '\n%smissing modules:%s %s\n' "$R" "$N" "${missing[*]}"
    printf 'Install them into THIS interpreter:\n\n'
    printf '  %s -m pip install -r requirements-dev.txt\n\n' "${PY[*]}"
    printf '(or re-run with --install, which does exactly that)\n'
    FAILED=1
  else
    run_job "py-lint (ruff)" "${PY[@]}" -m ruff check .
    run_job "py-format (black --check)" "${PY[@]}" -m black --check .

    # Exit code 5 is "no tests collected", which CI treats as a pass while
    # some packages are still stubs. Same guard here.
    job_pytest() {
      "${PY[@]}" -m pytest
      local c=$?
      [ $c -eq 5 ] && return 0
      return $c
    }
    run_job "py-test (pytest)" job_pytest
  fi

  job_import_sanity() {
    "${PY[@]}" -c "
import packages.schemas.python.entities as entities
import packages.schemas.python.agent_io as agent_io
print('schema modules import cleanly:', entities.__name__, agent_io.__name__)
" || return 1
    local dir
    for dir in agents apps/api packages/ai packages/metrics packages/common; do
      if find "$dir" -name '*.py' 2>/dev/null | grep -q .; then
        echo "Compiling $dir ..."
        "${PY[@]}" -m compileall -q "$dir" || return 1
      fi
    done
    return 0
  }
  run_job "build (python import sanity)" job_import_sanity
fi

# --------------------------------------------------------------------------
# TypeScript jobs
# --------------------------------------------------------------------------
if want ts; then
  if ! command -v pnpm >/dev/null 2>&1; then
    printf '\n%smissing: pnpm%s — run `corepack enable` (the version is pinned in package.json)\n' "$R" "$N"
    RESULTS+=("${R}FAIL${N}  pnpm not installed")
    FAILED=1
  else
    printf '\n%s=== pnpm install --frozen-lockfile ===%s\n' "$B" "$N"
    if ! pnpm install --frozen-lockfile; then
      RESULTS+=("${R}FAIL${N}  pnpm install — every ts job below depends on this")
      FAILED=1
      printf '\n%sIf that failed with "is not recognized as an internal or external%s\n' "$Y" "$N"
      printf '%scommand" pointing into AppData\\Local\\pnpm\\.tools, the self-managed%s\n' "$Y" "$N"
      printf '%spnpm matching package.json'"'"'s packageManager field is corrupt. Delete%s\n' "$Y" "$N"
      printf '%sit and let pnpm refetch:%s\n\n' "$Y" "$N"
      printf '  rm -rf ~/AppData/Local/pnpm/.tools/pnpm\n\n'
      printf 'Failing that, `corepack enable && corepack prepare pnpm@12.3.4 --activate`.\n'
    else
      PNPM_READY=true
      if [ -z "$has_ts" ]; then
        skip_job "ts-lint (eslint)" "no tracked TS files — workflow skips this too"
      else
        job_eslint() {
          if [ -f apps/web/package.json ]; then pnpm --filter web lint || return 1; fi
          pnpm exec eslint packages/schemas/typescript --no-error-on-unmatched-pattern
        }
        run_job "ts-lint (eslint)" job_eslint
      fi

      if [ -z "$has_tscss" ]; then
        skip_job "ts-format (prettier)" "no tracked TS/CSS files — workflow skips this too"
      else
        run_job "ts-format (prettier --check)" pnpm run format:check
      fi

      if [ -z "$has_webtests" ]; then
        skip_job "ts-test (vitest)" "no tracked apps/web test files — workflow skips this too"
      else
        run_job "ts-test (vitest)" pnpm --filter web test
      fi
    fi
  fi

  if [ -f apps/web/package.json ]; then
    if $PNPM_READY; then
      run_job "build (next build)" pnpm --filter web build
    else
      skip_job "build (next build)" "dependencies aren't installed — fix pnpm install first"
    fi
  fi
fi

# --------------------------------------------------------------------------
# Non-blocking jobs — `continue-on-error: true` in the workflow, so a failure
# here never turns a PR red. Off unless you ask for them.
# --------------------------------------------------------------------------
if $RUN_NONBLOCKING && [ ${#PY[@]} -gt 0 ]; then
  if py_has_module mypy; then
    printf '\n%s=== py-typecheck (mypy, non-blocking) ===%s\n' "$B" "$N"
    "${PY[@]}" -m mypy packages/schemas/python || true
    RESULTS+=("${Y}INFO${N}  py-typecheck — non-blocking in CI")
  fi
  if py_has_module pip_audit; then
    printf '\n%s=== audit (pip-audit, non-blocking) ===%s\n' "$B" "$N"
    "${PY[@]}" -m pip_audit -r requirements-dev.txt || true
    RESULTS+=("${Y}INFO${N}  pip-audit — non-blocking in CI")
  fi
fi

# --------------------------------------------------------------------------
printf '\n%s=== summary ===%s\n' "$B" "$N"
for r in "${RESULTS[@]}"; do printf '  %s\n' "$r"; done

if [ "$FAILED" -ne 0 ]; then
  printf '\n%sSomething a PR check would catch failed.%s\n' "$R" "$N"
  exit 1
fi
printf '\n%sAll blocking jobs passed.%s\n' "$G" "$N"
printf 'Note: this ran on your machine, not ubuntu-latest. If CI still\n'
printf 'disagrees, re-run that one job under act (see local-development.md).\n'
