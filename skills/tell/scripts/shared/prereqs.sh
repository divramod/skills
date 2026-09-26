# Shared by every scripts/<source>/{check,install}-prerequisites.sh (sourced, not run). Bash 3.2 compatible.
#
# A check script sets SOURCE, REQUIRED=(tool ...) and OPTIONAL=("tool:why" ...), sources this file and calls
# `check_main "$@"`. `check-prerequisites.sh --list` prints its tools (one per line), which is how the install
# script knows what to install: `install_main "$HERE" "$@"`.

have() { command -v "$1" >/dev/null 2>&1; }

# How to install a tool by hand (shown next to MISSING).
hint() {
  case "$1" in
    yt-dlp) echo "brew install yt-dlp" ;;
    ffmpeg|ffprobe) echo "brew install ffmpeg" ;;
    python3) echo "brew install python" ;;
    uv|uvx) echo "brew install uv" ;;
    gh) echo "brew install gh && gh auth login" ;;
    npx|node) echo "brew install node" ;;
    pdftotext) echo "brew install poppler" ;;
    pandoc) echo "brew install pandoc" ;;
    *) echo "install $1 and put it on PATH" ;;
  esac
}

# Homebrew / apt-get package that provides a tool ("" = installed another way).
brew_pkg() {
  case "$1" in
    ffprobe) echo ffmpeg ;; python3) echo python ;; uvx) echo uv ;; npx) echo node ;; pdftotext) echo poppler ;;
    *) echo "$1" ;;
  esac
}
apt_pkg() {
  case "$1" in
    ffmpeg|ffprobe) echo ffmpeg ;; python3) echo python3 ;; npx|node) echo "nodejs npm" ;;
    pdftotext) echo poppler-utils ;; pandoc) echo pandoc ;; gh) echo gh ;; *) echo "" ;;
  esac
}

# check_main [--list]: print ok / MISSING / missing lines; exit 1 when a required tool is missing.
check_main() {
  local t entry why missing=0
  if [ "${1:-}" = "--list" ]; then
    for t in ${REQUIRED[@]+"${REQUIRED[@]}"}; do echo "$t"; done
    for entry in ${OPTIONAL[@]+"${OPTIONAL[@]}"}; do echo "${entry%%:*}"; done
    return 0
  fi
  for t in ${REQUIRED[@]+"${REQUIRED[@]}"}; do
    if have "$t"; then
      echo "ok       $t"
    else
      echo "MISSING  $t (required by $SOURCE) -> $(hint "$t")" >&2
      missing=1
    fi
  done
  for entry in ${OPTIONAL[@]+"${OPTIONAL[@]}"}; do
    t="${entry%%:*}"; why="${entry#*:}"
    if have "$t"; then
      echo "ok       $t"
    else
      echo "missing  $t (optional, $why) -> $(hint "$t")" >&2
    fi
  done
  if [ "$missing" -ne 0 ]; then
    echo "Install the missing $SOURCE tools with: $HERE/install-prerequisites.sh" >&2
    return 1
  fi
  if [ "${#REQUIRED[@]}" -eq 0 ] && [ "${#OPTIONAL[@]}" -eq 0 ]; then
    echo "ok       ($SOURCE needs no external tools)"
  fi
  return 0
}

# install_main <dir> [--upgrade]: install the missing tools of <dir>/check-prerequisites.sh (Homebrew first, then
# apt-get), then run the check. --upgrade also upgrades yt-dlp (YouTube breaks old versions quickly).
install_main() {
  local dir="$1" upgrade=0 t pkg missing=() brew_pkgs=() apt_pkgs=() need_uv=0 need_ytdlp=0
  shift
  [ "${1:-}" = "--upgrade" ] && upgrade=1
  for t in $("$dir/check-prerequisites.sh" --list); do
    have "$t" || missing+=("$t")
  done
  if [ "${#missing[@]}" -eq 0 ] && { [ "$upgrade" -eq 0 ] || ! have yt-dlp; }; then
    "$dir/check-prerequisites.sh"
    return
  fi
  for t in ${missing[@]+"${missing[@]}"}; do
    if have brew; then
      pkg="$(brew_pkg "$t")"
      case " ${brew_pkgs[*]-} " in *" $pkg "*) ;; *) brew_pkgs+=("$pkg") ;; esac
    else
      case "$t" in
        uv|uvx) need_uv=1 ;;
        yt-dlp) need_ytdlp=1 ;;
        *) pkg="$(apt_pkg "$t")"; [ -n "$pkg" ] && apt_pkgs+=($pkg) ;;
      esac
    fi
  done
  if have brew; then
    if [ "${#brew_pkgs[@]}" -gt 0 ]; then
      echo "brew install ${brew_pkgs[*]}"
      brew install "${brew_pkgs[@]}"
    fi
    if [ "$upgrade" -eq 1 ] && have yt-dlp; then brew upgrade yt-dlp || true; fi
  elif have apt-get; then
    local sudo=""; [ "$(id -u)" -ne 0 ] && sudo="sudo"
    { [ "$need_uv" -eq 1 ] || [ "$need_ytdlp" -eq 1 ]; } && ! have curl && apt_pkgs+=(curl)
    if [ "${#apt_pkgs[@]}" -gt 0 ]; then
      $sudo apt-get update && $sudo apt-get install -y "${apt_pkgs[@]}"
    fi
    export PATH="$HOME/.local/bin:$PATH"  # where uv and `uv tool install` put their commands
    if { [ "$need_uv" -eq 1 ] || [ "$need_ytdlp" -eq 1 ]; } && ! have uv; then
      echo "installing uv (https://astral.sh/uv)"
      curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    if [ "$need_ytdlp" -eq 1 ]; then
      uv tool install "yt-dlp[default]"
    elif [ "$upgrade" -eq 1 ] && have yt-dlp; then
      uv tool upgrade yt-dlp || echo "upgrade yt-dlp manually (it was not installed via uv)" >&2
    fi
  else
    echo "error: neither Homebrew nor apt-get found. Install these by hand:" >&2
    for t in ${missing[@]+"${missing[@]}"}; do echo "  $t: $(hint "$t")" >&2; done
    return 1
  fi
  # a folder's install script may define after_install (e.g. download pinned packages now, not on first use)
  if declare -F after_install >/dev/null; then after_install; fi
  "$dir/check-prerequisites.sh"
}
