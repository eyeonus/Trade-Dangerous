#!/usr/bin/env bash

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

process_file() {
  local file="$1"
  local tmp

  # Only operate on regular files
  [[ -f "$file" ]] || return 0

  tmp="$(mktemp -- "${file}.fix_indent.XXXXXX")" || {
    echo "fix_indent: mktemp failed for: $file" >&2
    return 1
  }

  # AWK filter:
  # - Convert tabs to 4 spaces
  # - Collapse blank runs to a single indented blank line (indent from next non-blank line)
  # - Drop trailing blanks at EOF
  # - Preserve CRLF if present
  awk '
    BEGIN { pending_blank = 0; use_crlf = 0 }

    function emit(s) {
      if (use_crlf) print s "\r";
      else          print s;
    }

    {
      s = $0
      if (sub(/\r$/, "", s)) use_crlf = 1

      gsub(/\t/, "    ", s)

      # whitespace-only line => treat as blank
      if (s ~ /^[ ]*$/) {
        pending_blank = 1
        next
      }

      # if we have pending blanks, emit exactly one blank indented to this line
      if (pending_blank) {
        match(s, /^[ ]*/)
        emit(substr(s, RSTART, RLENGTH))
        pending_blank = 0
      }

      emit(s)
    }

    END {
      # If file ends with blanks, emit nothing (no blank lines at/beyond EOF)
    }
  ' "$file" > "$tmp"

  if [[ $? -ne 0 ]]; then
    echo "fix_indent: awk failed for: $file" >&2
    rm -f -- "$tmp"
    return 1
  fi

  # Avoid touching files that would be unchanged
  if cmp -s -- "$file" "$tmp"; then
    rm -f -- "$tmp"
    return 0
  fi

  # Overwrite in place (preserves mode/owner; updates mtime)
  if ! cat -- "$tmp" > "$file"; then
    echo "fix_indent: write failed for: $file" >&2
    rm -f -- "$tmp"
    return 1
  fi

  rm -f -- "$tmp"
  return 0
}

main() {
  local recursive=0
  local target=""

  if [[ $# -eq 0 ]]; then
    usage >&2
    exit 2
  fi

  case "$1" in
    -h)
      usage
      exit 0
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
        exit 2
      fi
      ;;
    -*)
      usage >&2
      exit 2
      ;;
    *)
      if [[ $# -ne 1 ]]; then
        usage >&2
        exit 2
      fi
      target="$1"
      ;;
  esac

  if [[ $recursive -eq 0 ]]; then
    # Single file mode
    process_file "$target" || exit $?
    exit 0
  fi

  # Recursive mode
  if [[ ! -e "$target" ]]; then
    echo "fix_indent: path not found: $target" >&2
    exit 1
  fi

  local rc=0
  while IFS= read -r -d '' f; do
    process_file "$f" || rc=1
  done < <(find "$target" -type f -name '*.py' -print0)

  exit $rc
}

main "$@"
