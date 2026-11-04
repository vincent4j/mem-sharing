#!/bin/sh
# 把合成对话材料布置到专用临时 HOME（仅创建/复制文件，不执行任何共享命令、
# 不写真实 HOME、绝不覆盖任何已有文件）。
# 用法：
#   stage-synthetic-home.sh            —— 自行 mktemp 新建系统临时目录（推荐）
#   stage-synthetic-home.sh /专用空目录 —— 只接收本次专用、当前为空的真实目录
# 拒绝条件（拒绝时零写，目标保持原样）：
#   目标或其任一祖先为符号链接（含悬空，用 -L 判定，不用 -e）；
#   目标已存在任何内容（含隐藏文件）；目标不是目录或不存在。
# 自行 mktemp 生成的目录为本脚本当轮新建（随机名、私有权限），无法被预置
# 链接，故只须再验自身非链接且为空；macOS 系统临时区祖先含 /var 等系统
# 链接属正常，不构成写入风险，用户显式传入的目录才做全祖先检查。
set -eu

fail() { echo "拒绝：$1" >&2; exit 2; }

check_fresh_dir() {  # 自生成目录：仅验自身非链接且为空
    [ -L "$1" ] && fail "目标是符号链接：$1"
    [ -d "$1" ] || fail "不是目录：$1"
    [ -z "$(ls -A "$1")" ] || fail "目录非空：$1"
}

check_user_dir() {  # 用户显式传入：自身与全部祖先均不得为链接，且必须为空
    [ -L "$1" ] && fail "目标是符号链接：$1"
    [ -d "$1" ] || fail "目标不存在或不是目录：$1"
    [ -z "$(ls -A "$1")" ] || fail "目录非空（拒绝覆盖任何已有内容）：$1"
    p=$(CDPATH= cd -- "$1" && pwd -P)   # 解析后逐级回查真实路径无链接
    [ "$p" = "$1" ] || fail "路径含符号链接成分：$1 -> $p"
    anc=$(dirname -- "$1")
    while [ "$anc" != "/" ]; do
        [ -L "$anc" ] && fail "祖先为符号链接：$anc"
        [ -d "$anc" ] || fail "祖先缺失：$anc"
        anc=$(dirname -- "$anc")
    done
}

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
if [ $# -eq 0 ]; then
    TARGET=$(mktemp -d "${TMPDIR:-/tmp}/memshare-dialogue.XXXXXX")
    check_fresh_dir "$TARGET"
elif [ $# -eq 1 ]; then
    TARGET=$1
    case "$TARGET" in /*) ;; *) fail "必须传绝对路径";; esac
    check_user_dir "$TARGET"
else
    fail "参数过多；无参数即自动创建专用临时目录"
fi

# 全部检查通过后才写入；三个子目录均为新建，cp 目标均为新建文件。
mkdir "$TARGET/.codex" "$TARGET/.claude" "$TARGET/.workbuddy"
cp "$HERE/sources/codex-AGENTS.md" "$TARGET/.codex/AGENTS.md"
cp "$HERE/sources/claude-CLAUDE.md" "$TARGET/.claude/CLAUDE.md"
cp "$HERE/sources/workbuddy-MEMORY.md" "$TARGET/.workbuddy/MEMORY.md"
echo "staged: $TARGET"
for f in "$TARGET/.codex/AGENTS.md" "$TARGET/.claude/CLAUDE.md" \
         "$TARGET/.workbuddy/MEMORY.md"; do
    /usr/bin/shasum -a 256 "$f"
done
