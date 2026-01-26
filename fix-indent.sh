#!/usr/bin/env bash
set -u

usage() {
  cat <<'EOF'
Usage:
  fix_indent <filename>
      Fix a single file in-place.

  fix_indent -R <folder>
      Recurse through <folder>, fixing all *.py files.

  fix_indent -R
      Recurse from the current directory, fixing all *.py files.

  fix_indent -h
      Show this help and exit.

Rules enforced:
  - Replace every tab with 4 spaces.
  - Collapse multiple blank lines to a single blank line.
  - That blank line must be indented to match the immediately following non-blank line.
  - Remove blank lines at EOF (no trailing blank lines).
EOF
}

# If sourced, "exit" would kill the caller shell. Use safe_exit.
safe_exit() {
  local code="${1:-0}"
  if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return "$code"
  fi
  exit "$code"
}

process_file() {
  local file="$1"
  local tmp dir

  [[ -f "$file" ]] || return 0

  dir="$(dirname -- "$file")"
  tmp="$(mktemp --tmpdir="$dir" ".fix_indent.XXXXXX")" || {
    echo "fix_indent: mktemp failed for: $file" >&2
    return 1
  }

  awk '
    BEGIN { pending_blank = 0; use_crlf = 0 }

    function emit(s) {
      if (use_crlf) print s "\r";
      else          print s;
    }

    {
      s = $0
      if (sub(/\r$/, "", s)) use_crlf = 1

      # Tabs are forbidden: replace with 4 spaces (everywhere)
      gsub(/\t/, "    ", s)

      # whitespace-only line => treat as blank (after tab expansion this is spaces-only)
      if (s ~ /^[ ]*$/) {
        pending_blank = 1
        next
      }

      # If we have pending blanks, emit exactly one blank indented to this line
      if (pending_blank) {
        match(s, /^[ ]*/)
        emit(substr(s, RSTART, RLENGTH))
        pending_blank = 0
      }

      emit(s)
    }

    END {
      # Trailing blanks at EOF are dropped (no output here)
    }
  ' "$file" > "$tmp"

  if [[ $? -ne 0 ]]; then
    echo "fix_indent: awk failed for: $file" >&2
    rm -f -- "$tmp"
    return 1
  fi

  if cmp -s -- "$file" "$tmp"; then
    rm -f -- "$tmp"
    return 0
  fi

  # Preserve permissions where possible
  chmod --reference="$file" "$tmp" 2>/dev/null || true
  chown --reference="$file" "$tmp" 2>/dev/null || true

  # Atomic replace
  if ! mv -f -- "$tmp" "$file"; then
    echo "fix_indent: replace failed for: $file" >&2
    rm -f -- "$tmp"
    return 1
  fi

  return 0
}

main() {
  local recursive=0
  local target=""

  if [[ $# -eq 0 ]]; then
    usage >&2
    safe_exit 2
  fi

  case "$1" in
    -h)
      usage
      safe_exit 0
      ;;
    -R)
      recursive=1
      shift
      if [[ $# -ge 1 ]]; then
        target="$1"
        shift
      else
        target="."
      fi
      if [[ $# -ne 0 ]]; then
        usage >&2
        safe_exit 2
      fi
      ;;
    -*)
      usage >&2
      safe_exit 2
      ;;
    *)
      if [[ $# -ne 1 ]]; then
        usage >&2
        safe_exit 2
      fi
      target="$1"
      ;;
  esac

  if [[ $recursive -eq 0 ]]; then
    process_file "$target" || safe_exit $?
    safe_exit 0
  fi

  if [[ ! -e "$target" ]]; then
    echo "fix_indent: path not found: $target" >&2
    safe_exit 1
  fi

  local rc=0
  while IFS= read -r -d '' f; do
    process_file "$f" || rc=1
  done < <(find "$target" -type f -name '*.py' -print0)

  safe_exit "$rc"
}

# If someone sources it, don't run it implicitly; tell them what to do.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "fix_indent: don’t source this script. Run it: ./fix_indent [args]" >&2
  return 2
fi

main "$@"
