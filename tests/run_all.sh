#!/bin/sh
# Runs every test in tests/ and prints a summary. Each test prints PASS/FAIL
# lines and exits non-zero when something failed.
#   ./tests/run_all.sh            everything
#   ./tests/run_all.sh theme      only the tests whose name contains "theme"
cd "$(dirname "$0")/.." || exit 1
pattern="${1:-}"
pass=0
fail=0
failed=""
start=$(date +%s)
for t in tests/*_test.py; do
    name=$(basename "$t")
    if [ -n "$pattern" ]; then
        case "$name" in
            *"$pattern"*) ;;
            *) continue ;;
        esac
    fi
    out=$(python3 "$t" 2>&1)
    rc=$?
    bad=$(printf '%s\n' "$out" | grep -c '^FAIL')
    if [ "$rc" -eq 0 ] && [ "$bad" -eq 0 ]; then
        pass=$((pass + 1))
        printf 'ok    %s\n' "$name"
    else
        fail=$((fail + 1))
        failed="$failed $name"
        printf 'FAIL  %s (exit %s, %s failed checks)\n' "$name" "$rc" "$bad"
        printf '%s\n' "$out" | grep -A3 '^FAIL' | sed 's/^/      /'
    fi
done
echo "----"
echo "$pass passed, $fail failed in $(( $(date +%s) - start ))s"
[ -z "$failed" ] || echo "failed:$failed"
[ "$fail" -eq 0 ]
