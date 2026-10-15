#!/usr/bin/env bash
# 按 tasks/cards.yaml 为一张任务卡准备工作目录和设置，然后打印启动命令。
#
# 用法：
#   scripts/start-card.sh <卡号>              准备这张卡
#   scripts/start-card.sh <卡号> --dry-run    只打印将要做什么，不动文件
#   scripts/start-card.sh T14-B <调优包>      packet 模式需要指定调优包
#   scripts/start-card.sh --list              列出所有卡（id|owner|mode|repo|card|after|note）
#   scripts/start-card.sh <卡号> --refresh-settings
#                                             模板改了之后，用新模板重写已存在 clone 的
#                                             .claude/settings.local.json，不重新克隆。
#                                             **不要在一张卡进行中用**——中途换隔离设置会让
#                                             这张卡的 isolation-check.md 不再描述实际会话。
#
# 由**用户在终端**运行；agent 的会话里不要运行（会话里禁止 git clone）。
# 所有路径只从环境变量来：SEMDEBT_MAIN_DIR / SEMDEBT_EVAL_DIR / SEMDEBT_DATA_DIR，
# 卡片目录默认是主工作区的同级 cards/，可用 SEMDEBT_CARDS_DIR 覆盖。

set -euo pipefail

VENDOR_REPO_URL="https://github.com/cubedevinc/semantic-layer-benchmark"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MAIN_DIR=${SEMDEBT_MAIN_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}
EVAL_DIR=${SEMDEBT_EVAL_DIR:-}
DATA_DIR=${SEMDEBT_DATA_DIR:-}
PARENT_DIR=$(dirname "$MAIN_DIR")
CARDS_DIR=${SEMDEBT_CARDS_DIR:-$PARENT_DIR/cards}
VENDOR_DIR=${SEMDEBT_VENDOR_DIR:-$PARENT_DIR/_vendor}
CARDS_FILE="$MAIN_DIR/tasks/cards.yaml"
TEMPLATE_DIR="$MAIN_DIR/templates"
FREEZE_TAG="semantic-v1"

DRY_RUN=0
REFRESH_SETTINGS=0

# ---------- 输出 ----------

die()  { printf '\033[31m错误：\033[0m%s\n' "$*" >&2; exit 1; }
warn() { printf '\033[33m注意：\033[0m%s\n' "$*" >&2; }
step() { printf '\033[36m==>\033[0m %s\n' "$*"; }

run() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

banner() {
  printf '\n'
  printf '\033[32m%s\033[0m\n' "下一步：复制下面这行到终端运行"
  printf '\n  %s\n\n' "$1"
}

# ---------- cards.yaml ----------

# 把 cards.yaml 里每张卡打成一行：id|owner|mode|repo|card|after|note
# 注意：tests/test_repo_layout.py 里有一份独立的 Python 实现，两者互相比对。
dump_cards() {
  [ -f "$CARDS_FILE" ] || die "找不到 $CARDS_FILE"
  awk '
    /^[[:space:]]*-[[:space:]]*\{/ {
      line = $0
      sub(/^[[:space:]]*-[[:space:]]*\{/, "", line)
      sub(/\}[[:space:]]*$/, "", line)
      n = 0; cur = ""; inq = 0
      for (i = 1; i <= length(line); i++) {
        c = substr(line, i, 1)
        if (c == "\"") { inq = !inq; continue }
        if (c == "," && !inq) { parts[++n] = cur; cur = ""; continue }
        cur = cur c
      }
      parts[++n] = cur
      delete kv
      for (j = 1; j <= n; j++) {
        p = parts[j]
        sub(/^[[:space:]]+/, "", p); sub(/[[:space:]]+$/, "", p)
        ci = index(p, ":")
        if (ci == 0) continue
        k = substr(p, 1, ci - 1); v = substr(p, ci + 1)
        sub(/^[[:space:]]+/, "", v); sub(/[[:space:]]+$/, "", v)
        kv[k] = v
      }
      if (kv["id"] == "") next
      printf "%s|%s|%s|%s|%s|%s|%s\n", kv["id"], kv["owner"], kv["mode"], kv["repo"], kv["card"], kv["after"], kv["note"]
      for (j = 1; j <= n; j++) delete parts[j]
    }
  ' "$CARDS_FILE"
}

# 大小写不敏感地找一张卡（cards.yaml 里有 T01a、T05b 这样的小写后缀）
find_card() {
  local want=$1
  dump_cards | awk -F'|' -v want="$want" 'tolower($1) == tolower(want) { print; exit }'
}

# ---------- 环境检查 ----------

need_env() {
  local name=$1 value=$2
  [ -n "$value" ] || die "环境变量 $name 没设置。见 START-HERE.md 第 4 步。"
  [ -d "$value" ] || die "$name 指向的目录不存在：$value"
}

need_clean_worktree() {
  local repo=$1
  [ "$DRY_RUN" = 1 ] && return 0
  if [ -n "$(git -C "$repo" status --porcelain)" ]; then
    warn "$repo 有未提交的改动。继续之前先提交或暂存，否则新分支会带上它们。"
  fi
}

require_g1() {
  if ! git -C "$MAIN_DIR" rev-parse -q --verify "refs/tags/$FREEZE_TAG" >/dev/null 2>&1; then
    printf '\033[31m拒绝：\033[0m%s\n' "G1 之前不能用普通模式（主仓库还没有 tag ${FREEZE_TAG}）。" >&2
    printf '  语义层尚未冻结，普通模式会让这张卡看到题库，结果作废。\n' >&2
    printf '  如果 G1 刚过、tag 是在别处打的，先同步：git -C "%s" fetch --tags\n' "$MAIN_DIR" >&2
    exit 1
  fi
}

# dry-run 时不去读主仓库以外的仓库（T00 不得读取题库）
origin_url() {
  local repo=$1
  if [ "$DRY_RUN" = 1 ] && [ "$repo" != "$MAIN_DIR" ]; then
    printf '<%s 的 origin>\n' "$repo"
    return 0
  fi
  git -C "$repo" remote get-url origin 2>/dev/null || die "$repo 没有 origin 远端。"
}

# ---------- 准备工作目录 ----------

# clone_repo <源仓库> <目标目录> <分支名>
# 目标目录已存在时不覆盖，只提示。
clone_repo() {
  local src_repo=$1 dest=$2 branch=$3
  if [ -e "$dest" ]; then
    warn "$dest 已存在，不覆盖。"
    printf '  要重做这张卡：先确认里面没有未推送的提交，再手动删除该目录后重跑本脚本。\n' >&2
    printf '  检查：git -C "%s" status && git -C "%s" log --oneline origin/main..HEAD\n' "$dest" "$dest" >&2
    return 1
  fi
  local url
  url=$(origin_url "$src_repo")
  step "克隆 $url → $dest"
  run mkdir -p "$(dirname "$dest")"
  run git clone "$url" "$dest"
  step "新建分支 $branch"
  run git -C "$dest" switch -c "$branch"
  if [ "$DRY_RUN" = 0 ] && [ ! -f "$dest/.claude/settings.json" ] && [ "$src_repo" = "$MAIN_DIR" ]; then
    warn "$dest 里没有 .claude/settings.json——隔离设置不会生效。确认种子文件已推到 origin。"
  fi
  return 0
}

# branch_in_place <仓库> <分支名>：在现有工作树里切到新分支（Codex 的题库卡）
branch_in_place() {
  local repo=$1 branch=$2
  need_clean_worktree "$repo"
  if [ "$DRY_RUN" = 1 ]; then
    step "在 ${repo} 新建并切到分支 ${branch}"
    printf '  [dry-run] git -C "%s" switch -c %s\n' "$repo" "$branch"
    return 0
  fi
  if git -C "$repo" rev-parse -q --verify "refs/heads/$branch" >/dev/null 2>&1; then
    warn "分支 $branch 已存在，切过去而不新建。"
    step "切到 $branch"
    run git -C "$repo" switch "$branch"
  else
    step "在 $repo 新建并切到分支 $branch"
    run git -C "$repo" switch -c "$branch"
  fi
}

# write_settings <目标目录> <模板文件> [no-data]
# 把模板里的 ${SEMDEBT_*} 换成绝对路径，写成 .claude/settings.local.json。
write_settings() {
  local dest=$1 template=$2 no_data=${3:-}
  [ -f "$template" ] || die "找不到模板 $template"
  local out="$dest/.claude/settings.local.json"
  step "写设置 ${out}（模板 $(basename "$template")${no_data:+，去掉数据目录放行}）"
  if [ "$DRY_RUN" = 1 ]; then
    printf '  [dry-run] 内容预览：\n'
    render_settings "$template" "$no_data" | sed 's/^/    /'
    return 0
  fi
  mkdir -p "$dest/.claude"
  render_settings "$template" "$no_data" > "$out"
}

render_settings() {
  local template=$1 no_data=${2:-}
  local body
  body=$(cat "$template")
  if [ -n "$no_data" ]; then
    # packet 模式：去掉数据目录的放行
    body=$(printf '%s\n' "$body" | sed '/"additionalDirectories"/d')
  fi
  printf '%s\n' "$body" \
    | sed -e "s|\${SEMDEBT_DATA_DIR}|$DATA_DIR|g" \
          -e "s|\${SEMDEBT_EVAL_DIR}|$EVAL_DIR|g" \
          -e "s|\${SEMDEBT_MAIN_DIR}|$MAIN_DIR|g"
}

# ---------- 各模式 ----------

mode_main_checkout() {
  local id=$1 card=$2
  step "$id 是主工作区的卡，不需要单独的工作目录。"
  printf '  卡片：%s/%s\n' "$MAIN_DIR" "$card"
  banner "cd \"$MAIN_DIR\" && claude \"执行任务卡 $id\""
}

mode_claude_clone() {
  local id=$1 card=$2 template=$3 strict_mcp=${4:-}
  need_env SEMDEBT_DATA_DIR "$DATA_DIR"
  [ "$template" = "$TEMPLATE_DIR/claude-settings.blind.json" ] || need_env SEMDEBT_EVAL_DIR "$EVAL_DIR"
  local dest="$CARDS_DIR/$id"
  if clone_repo "$MAIN_DIR" "$dest" "$id-work"; then
    write_settings "$dest" "$template"
  fi
  printf '  卡片：%s/%s\n' "$dest" "$card"
  banner "cd \"$dest\" && claude $(mcp_flag "$strict_mcp")\"执行任务卡 $id\""
  printf '提示：第一次在新目录启动 Claude Code 会问是否信任这个文件夹，选「是」，否则项目设置不生效。\n'
  mcp_note "$strict_mcp"
}

# 盲模式（含 packet）必须零 MCP server。MCP 工具不受项目 deny 的完全管辖，能联网的 server
# （网页搜索、浏览器自动化、Notion 的 fetch）等于绕过 WebSearch/WebFetch 的禁令。
# 模板里的 deny 是黑名单，只挡已知的 server；--strict-mcp-config 才是物理手段。
mcp_flag() {
  [ -n "$1" ] && printf -- '--strict-mcp-config '
  return 0
}

mcp_note() {
  [ -n "$1" ] || return 0
  printf '\n盲模式为什么带 --strict-mcp-config：MCP 工具不受项目 deny 的完全管辖，能联网的 server\n'
  printf '（网页搜索、浏览器自动化、Notion 的 fetch）会绕过 WebSearch/WebFetch 的禁令。这个标志让会话\n'
  printf '不加载任何 MCP server。不要把它删掉——删了这张卡的结果作废。\n'
  printf 'agent 开工第一步会自己核实「可用的 MCP 工具为空」，见 scripts/verify-isolation.md 的 A11。\n'
}

mode_open_eval() {
  local id=$1 card=$2
  need_env SEMDEBT_EVAL_DIR "$EVAL_DIR"
  need_env SEMDEBT_DATA_DIR "$DATA_DIR"
  require_g1
  local dest="$CARDS_DIR/$id"
  clone_repo "$EVAL_DIR" "$dest" "$id-work" || true
  printf '  卡片：%s/%s\n' "$dest" "$card"
  banner "cd \"$dest\" && claude --add-dir \"$DATA_DIR\" \"执行任务卡 $id\""
}

mode_packet() {
  local id=$1 packet=${2:-}
  local dest="$CARDS_DIR/$id"
  [ -n "$packet" ] || die "packet 模式要指定调优包：scripts/start-card.sh $id <调优包名或路径>（取自 $MAIN_DIR/build/tuning-packet/）"
  local packet_path="$packet"
  [ -e "$packet_path" ] || packet_path="$MAIN_DIR/build/tuning-packet/$packet"
  [ -e "$packet_path" ] || die "找不到调优包：${packet}（也不在 $MAIN_DIR/build/tuning-packet/ 下）"
  if [ -e "$dest" ]; then
    warn "$dest 已存在，不覆盖。确认无用后手动删除再重跑。"
  else
    step "建调优包目录 ${dest}（不是 git clone）"
    run mkdir -p "$dest"
    step "复制 semantic/ 当前内容"
    run cp -R "$MAIN_DIR/semantic" "$dest/semantic"
    step "复制调优包 $packet_path"
    run cp -R "$packet_path" "$dest/tuning-packet"
    step "复制项目设置 .claude/settings.json（不是 clone，要手动带上沙箱设置）"
    run mkdir -p "$dest/.claude"
    run cp "$MAIN_DIR/.claude/settings.json" "$dest/.claude/settings.json"
    write_settings "$dest" "$TEMPLATE_DIR/claude-settings.blind.json" no-data
  fi
  printf '  B 角只读调优包和 semantic/：没有 git 远端，不放行数据目录，禁止网页搜索与抓取。\n'
  banner "cd \"$dest\" && claude --strict-mcp-config \"执行任务卡 $id\""
  mcp_note strict
}

mode_codex_eval() {
  local id=$1 card=$2
  need_env SEMDEBT_EVAL_DIR "$EVAL_DIR"
  branch_in_place "$EVAL_DIR" "$id-work"
  printf '  卡片：%s/%s\n' "$EVAL_DIR" "$card"
  banner "cd \"$EVAL_DIR\" && codex \"执行任务卡 $id\""
}

mode_codex_main() {
  local id=$1 card=$2
  local dest="$CARDS_DIR/$id"
  clone_repo "$MAIN_DIR" "$dest" "$id-work" || true
  printf '  卡片：%s/%s（不写 Claude Code 设置，Codex 自己的沙箱由它自己管）\n' "$dest" "$card"
  if ! git -C "$MAIN_DIR" rev-parse -q --verify "refs/tags/$FREEZE_TAG" >/dev/null 2>&1; then
    warn "G1 之前：如果这个会话要读主仓库 semantic/ 下除 conventions.md 以外的文件，拒绝它。"
  fi
  banner "cd \"$dest\" && codex \"执行任务卡 $id\""
}

mode_codex_root() {
  local id=$1 card=$2
  need_env SEMDEBT_EVAL_DIR "$EVAL_DIR"
  if [ "$(dirname "$EVAL_DIR")" != "$PARENT_DIR" ]; then
    warn "题库仓库不在主仓库的同级目录，启动命令里改用绝对路径。"
  fi
  step "克隆外部基准 → $VENDOR_DIR/semantic-layer-benchmark"
  if [ -e "$VENDOR_DIR/semantic-layer-benchmark" ]; then
    warn "$VENDOR_DIR/semantic-layer-benchmark 已存在，不覆盖。"
  else
    run mkdir -p "$VENDOR_DIR"
    run git clone "$VENDOR_REPO_URL" "$VENDOR_DIR/semantic-layer-benchmark"
  fi
  clone_repo "$MAIN_DIR" "$CARDS_DIR/$id-main" "$id-vendor-ddl" || true
  branch_in_place "$EVAL_DIR" "$id-work"
  printf '\n  这张卡同时往两个仓库提交，所以在上一级启动：\n'
  printf '    题库仓库（本卡分支 %s-work）：%s\n' "$id" "$EVAL_DIR"
  printf '    主仓库的 clone（分支 %s-vendor-ddl，放建表 DDL 和许可）：%s\n' "$id" "$CARDS_DIR/$id-main"
  printf '    外部基准（只读）：%s/semantic-layer-benchmark\n' "$VENDOR_DIR"
  local card_ref="$(basename "$EVAL_DIR")/$card"
  [ "$(dirname "$EVAL_DIR")" = "$PARENT_DIR" ] || card_ref="$EVAL_DIR/$card"
  banner "cd \"$PARENT_DIR\" && codex \"执行任务卡 ${id}，卡片在 $card_ref\""
}

# 用当前模板重写已存在 clone 的 settings.local.json。模板改了之后用。
refresh_settings() {
  local id=$1 mode=$2
  local dest="$CARDS_DIR/$id"
  [ -d "$dest" ] || die "${dest} 不存在，没有可刷新的设置。先正常跑一次 start-card.sh ${id}。"
  local template no_data=""
  case $mode in
    blind)  template="$TEMPLATE_DIR/claude-settings.blind.json" ;;
    open)   require_g1; template="$TEMPLATE_DIR/claude-settings.open.json" ;;
    packet) template="$TEMPLATE_DIR/claude-settings.blind.json"; no_data=no-data ;;
    *)      die "模式 ${mode} 没有 Claude Code 设置文件可刷新。" ;;
  esac
  need_env SEMDEBT_DATA_DIR "$DATA_DIR"
  [ "$mode" = blind ] || [ "$mode" = packet ] || need_env SEMDEBT_EVAL_DIR "$EVAL_DIR"
  if [ "$DRY_RUN" = 0 ] && [ -n "$(git -C "$dest" status --porcelain 2>/dev/null)" ]; then
    warn "${dest} 有未提交的改动——这张卡多半正在进行中。"
    printf '  在一张卡进行中换隔离设置，会让它的 isolation-check.md 不再描述实际会话。\n' >&2
    printf '  确实要刷新就先提交或暂存，再重跑本命令。\n' >&2
    exit 1
  fi
  write_settings "$dest" "$template" "$no_data"
  printf '\n设置已按当前模板重写。重启该目录的 Claude Code 才会生效：\n'
  banner "cd \"$dest\" && claude $(mcp_flag "$([ "$mode" = blind ] || [ "$mode" = packet ] && echo strict)")\"执行任务卡 $id\""
}

mode_windows() {
  local id=$1 card=$2
  step "$id 在 Windows 电脑上做。"
  printf '  卡片：主仓库的 %s（在 Windows 上也克隆两个仓库，步骤见卡片）\n' "$card"
  printf '  需要：Power BI Desktop（不要用公司租户）、Python、ADOMD.NET（例如 pyadomd）。\n'
  printf '  DAX 在 Desktop 打开 PBIP 后的本地 Analysis Services 端口上执行。\n'
  printf '  那台机器上用不了 Claude Code 时，按卡里写的替代做法。\n\n'
}

mode_user() {
  local id=$1 card=$2
  step "$id 由你自己做，没有 agent。"
  printf '  卡片：%s/%s\n\n' "$MAIN_DIR" "$card"
}

# ---------- 主流程 ----------

usage() {
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

main() {
  local id="" packet=""
  while [ $# -gt 0 ]; do
    case $1 in
      --list)    dump_cards; exit 0 ;;
      --dry-run) DRY_RUN=1 ;;
      --refresh-settings) REFRESH_SETTINGS=1 ;;
      -h|--help) usage 0 ;;
      -*)        die "不认识的参数：$1" ;;
      *)         if [ -z "$id" ]; then id=$1; else packet=$1; fi ;;
    esac
    shift
  done
  [ -n "$id" ] || usage 1

  need_env SEMDEBT_MAIN_DIR "$MAIN_DIR"

  local row
  row=$(find_card "$id")
  [ -n "$row" ] || die "cards.yaml 里没有卡号 ${id}。可用的卡：$(dump_cards | cut -d'|' -f1 | tr '\n' ' ')"

  local owner mode repo card after note
  IFS='|' read -r id owner mode repo card after note <<<"$row"

  printf '\n卡号 %s｜负责 %s｜模式 %s｜仓库 %s\n' "$id" "$owner" "$mode" "$repo"
  [ -n "$after" ] && printf '前置检查点：%s（没过就别开工）\n' "$after"
  [ -n "$note" ] && printf '备注：%s\n' "$note"
  [ "$DRY_RUN" = 1 ] && printf '（dry-run：只打印，不动文件）\n'
  printf '\n'

  if [ "$REFRESH_SETTINGS" = 1 ]; then
    refresh_settings "$id" "$mode"
    exit 0
  fi

  case $mode in
    main-checkout) mode_main_checkout "$id" "$card" ;;
    blind)         mode_claude_clone "$id" "$card" "$TEMPLATE_DIR/claude-settings.blind.json" strict ;;
    open)          require_g1; mode_claude_clone "$id" "$card" "$TEMPLATE_DIR/claude-settings.open.json" ;;
    open-eval)     mode_open_eval "$id" "$card" ;;
    packet)        mode_packet "$id" "$packet" ;;
    codex-eval)    mode_codex_eval "$id" "$card" ;;
    codex-main)    mode_codex_main "$id" "$card" ;;
    codex-root)    mode_codex_root "$id" "$card" ;;
    windows)       mode_windows "$id" "$card" ;;
    user)          mode_user "$id" "$card" ;;
    *)             die "cards.yaml 里的模式 $mode 没实现。" ;;
  esac
}

main "$@"
