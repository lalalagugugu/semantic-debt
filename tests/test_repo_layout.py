"""仓库自身约定的回归测试。不测模型输出，只测骨架、cards.yaml、模板和启动脚本。

cards.yaml 在这里用一份独立的 Python 解析器读，再和 scripts/start-card.sh --list
的输出比对：两份实现都在，改了一边忘了另一边就会红。
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CARDS_YAML = REPO / "tasks" / "cards.yaml"
BOARD = REPO / "tasks" / "BOARD.md"
START_CARD = REPO / "scripts" / "start-card.sh"

# AGENTS.md「目录」一节列出的目录，外加 tests/
SKELETON_DIRS = [
    "data",
    "docs",
    "vendor",
    "semantic",
    "render",
    "build",
    "harness",
    "runs",
    "reports",
    "decisions",
    "scripts",
    "tasks",
    "templates",
    "tests",
]

FIELDS = ("id", "owner", "mode", "repo", "card", "after", "note")


def parse_cards() -> list[dict[str, str]]:
    """独立实现：读 cards.yaml 里的 flow 风格行 `- {id: T00, owner: claude, ...}`。"""
    rows: list[dict[str, str]] = []
    for line in CARDS_YAML.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*-\s*\{(.*)\}\s*$", line)
        if not m:
            continue
        body = m.group(1)
        parts, cur, in_quotes = [], "", False
        for ch in body:
            if ch == '"':
                in_quotes = not in_quotes
                continue
            if ch == "," and not in_quotes:
                parts.append(cur)
                cur = ""
                continue
            cur += ch
        parts.append(cur)
        row = {f: "" for f in FIELDS}
        for part in parts:
            key, sep, value = part.partition(":")
            if not sep:
                continue
            row[key.strip()] = value.strip()
        if row["id"]:
            rows.append(row)
    return rows


@pytest.fixture(scope="module")
def cards() -> list[dict[str, str]]:
    rows = parse_cards()
    assert rows, "cards.yaml 里一张卡都没解析出来"
    return rows


# ---------- 骨架 ----------


@pytest.mark.parametrize("name", SKELETON_DIRS)
def test_skeleton_dir_exists_with_readme(name: str) -> None:
    d = REPO / name
    assert d.is_dir(), f"缺目录 {name}/（见 AGENTS.md「目录」）"
    assert (d / "README.md").is_file(), f"{name}/ 缺 README.md 说明用途"


def test_templates_exist() -> None:
    for f in ("decisions/open-questions.md", "runs/INDEX.md", "AGENTS.md", "pyproject.toml"):
        assert (REPO / f).is_file(), f"缺 {f}"


def test_gitignore_keeps_data_and_build_out() -> None:
    text = (REPO / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("data/raw/", "data/parquet/", "data/chdb/", "*.parquet",
                    ".claude/settings.local.json", ".env"):
        assert pattern in text, f".gitignore 少了 {pattern}（硬规则 4、5）"
    assert "build/*" in text, ".gitignore 要忽略 build/ 的产物"


def test_no_hardcoded_absolute_paths_in_code() -> None:
    """代码只通过环境变量找路径（AGENTS.md「环境」）。"""
    # 分段拼出来，免得本文件自己撞上这条规则
    pattern = re.compile("/" + "Users" + "/|/" + "home" + "/[a-z]")
    offenders = []
    for d in ("scripts", "render", "harness", "data", "tests"):
        for f in (REPO / d).rglob("*"):
            if not f.is_file() or f.suffix not in {".sh", ".py", ".sql", ".toml"}:
                continue
            if f.name == Path(__file__).name:
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{f.relative_to(REPO)}:{i}: {line.strip()}")
    assert not offenders, "写死了绝对路径：\n" + "\n".join(offenders)


def test_no_api_key_literals() -> None:
    """key 只从环境变量读，不得写进任何文件（硬规则 5）。"""
    offenders = []
    for f in REPO.rglob("*"):
        if ".git/" in str(f) or ".venv" in str(f) or not f.is_file():
            continue
        if f.suffix not in {".sh", ".py", ".md", ".toml", ".json", ".yaml", ".yml"}:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.search(r"sk-[A-Za-z0-9]{16,}", line):
                offenders.append(f"{f.relative_to(REPO)}:{i}")
    assert not offenders, f"疑似硬编码的 API key：{offenders}"


# ---------- cards.yaml ----------


def test_bash_and_python_parsers_agree(cards: list[dict[str, str]]) -> None:
    out = subprocess.run(
        ["bash", str(START_CARD), "--list"],
        capture_output=True, text=True, check=True, cwd=REPO,
    ).stdout.strip().splitlines()
    expected = ["|".join(row[f] for f in FIELDS) for row in cards]
    assert out == expected, "start-card.sh 的 cards.yaml 解析与测试里的实现不一致"


def test_card_ids_unique(cards: list[dict[str, str]]) -> None:
    ids = [row["id"] for row in cards]
    assert len(ids) == len(set(ids)), f"卡号重复：{ids}"


def test_main_repo_card_files_exist(cards: list[dict[str, str]]) -> None:
    """repo: main 的卡片必须在本仓库里；repo: eval 的在题库仓库，本仓库测不到。"""
    missing = [
        row["card"] for row in cards
        if row["repo"] == "main" and not (REPO / row["card"]).is_file()
    ]
    assert not missing, f"cards.yaml 指向的卡片文件不存在：{missing}"


def test_every_mode_is_implemented(cards: list[dict[str, str]]) -> None:
    script = START_CARD.read_text(encoding="utf-8")
    handled = set(re.findall(r"^\s{4}([a-z-]+)\)\s", script, flags=re.MULTILINE))
    modes = {row["mode"] for row in cards}
    assert modes <= handled, f"cards.yaml 用了 start-card.sh 没实现的模式：{modes - handled}"


def test_owner_and_repo_values_are_known(cards: list[dict[str, str]]) -> None:
    for row in cards:
        assert row["owner"] in {"claude", "codex", "user"}, row
        assert row["repo"] in {"main", "eval", "none"}, row


def test_blind_cards_are_claude_only(cards: list[dict[str, str]]) -> None:
    """盲任务只给 Claude Code（AGENTS.md 分工规则 2）。"""
    for row in cards:
        if row["mode"] in {"blind", "packet"}:
            assert row["owner"] == "claude", f"{row['id']} 是盲模式却不归 Claude Code"


def test_open_modes_gated_behind_g1(cards: list[dict[str, str]]) -> None:
    """普通模式能看到题库，必须在 G1 之后；start-card.sh 也要拦。"""
    script = START_CARD.read_text(encoding="utf-8")
    assert "require_g1" in script
    assert 'semantic-v1' in script
    for row in cards:
        if row["mode"] in {"open", "open-eval"}:
            assert row["after"] in {"G1", "G2", "G3"} or row["id"] in {"T14", "T19"}, (
                f"{row['id']} 用普通模式但没写前置检查点"
            )


def test_board_and_cards_cover_the_same_ids(cards: list[dict[str, str]]) -> None:
    board = BOARD.read_text(encoding="utf-8")
    board_ids = set(re.findall(r"^\|\s*\**(T\d+[a-z]?)\**\s*\|", board, flags=re.MULTILINE))
    yaml_ids = {row["id"] for row in cards}
    # T14-B 是 T14 的 B 角，BOARD 里并在 T14 一行
    yaml_base = {i.split("-")[0] for i in yaml_ids}
    assert board_ids <= yaml_base, f"BOARD 有而 cards.yaml 没有：{board_ids - yaml_base}"
    assert yaml_base <= board_ids, f"cards.yaml 有而 BOARD 没有：{yaml_base - board_ids}"


# ---------- 模板 ----------


@pytest.mark.parametrize("name", ["claude-settings.blind.json", "claude-settings.open.json"])
def test_template_renders_to_valid_json(name: str) -> None:
    raw = (REPO / "templates" / name).read_text(encoding="utf-8")
    rendered = (
        raw.replace("${SEMDEBT_DATA_DIR}", "/abs/data")
        .replace("${SEMDEBT_EVAL_DIR}", "/abs/eval")
        .replace("${SEMDEBT_MAIN_DIR}", "/abs/main")
    )
    assert "${" not in rendered, f"{name} 里有 start-card.sh 不认识的占位符"
    json.loads(rendered)


def test_blind_template_denies_eval_and_web() -> None:
    raw = (REPO / "templates" / "claude-settings.blind.json").read_text(encoding="utf-8")
    cfg = json.loads(
        raw.replace("${SEMDEBT_DATA_DIR}", "/abs/data")
        .replace("${SEMDEBT_EVAL_DIR}", "/abs/eval")
        .replace("${SEMDEBT_MAIN_DIR}", "/abs/main")
    )
    deny = cfg["permissions"]["deny"]
    assert "WebSearch" in deny and "WebFetch" in deny, "盲模式必须禁止上网（硬规则 1）"
    assert any("/abs/eval" in d for d in deny), "盲模式必须禁止读题库"
    assert any("runs-raw" in d for d in deny), "盲模式必须禁止读模型原始输出"
    assert "/abs/eval" in cfg["sandbox"]["filesystem"]["denyRead"]


def test_blind_template_blocks_mcp_servers() -> None:
    """MCP 工具不受项目 deny 之外的管辖，能联网的 server 会绕过 WebSearch/WebFetch。

    这是第二道黑名单；物理手段是启动命令里的 --strict-mcp-config，准绳是
    scripts/verify-isolation.md 的 A11（agent 自证可用 MCP 工具为空）。
    """
    cfg = json.loads((REPO / "templates" / "claude-settings.blind.json").read_text(encoding="utf-8"))
    deny = cfg["permissions"]["deny"]
    known_networked = {
        "mcp__dashscope-websearch",
        "mcp__chrome-devtools",
        "mcp__claude_ai_Notion",
        "mcp__claude_ai_Google_Drive",
    }
    missing = known_networked - set(deny)
    assert not missing, f"盲模板没挡住这些能联网的 MCP server：{missing}"


def test_blind_template_has_no_clone_local_runs_rule() -> None:
    """clone 自己的 runs/ 不设 deny；主工作区的 runs/ 仍然挡住。

    盲模式卡都在 G1 之前，而所有 run 都在 G1 之后，所以盲写期间 clone 的 runs/
    里只有 README.md 和 INDEX.md 两个文档，没有保护对象。而沙箱层会把
    Read(./runs/...) 落成 ./runs/*，连这两个文档一起挡住，使 B4「测试能跑」
    固定变红——收窄过两次都没解决。见 decisions/isolation-settings.md。
    """
    raw = (REPO / "templates" / "claude-settings.blind.json").read_text(encoding="utf-8")
    cfg = json.loads(raw)
    deny = cfg["permissions"]["deny"]
    assert not [d for d in deny if d.startswith("Read(./runs")], "clone 本地的 runs deny 应当已移除"
    assert any("runs/**" in d and "SEMDEBT_MAIN_DIR" in d for d in deny), "主工作区的 runs/ 仍须挡住"
    assert any("runs-raw" in d for d in deny), "模型原始输出仍须挡住"


def test_blind_and_packet_launch_with_strict_mcp_config() -> None:
    """盲模式与 packet 的启动命令必须带 --strict-mcp-config；普通模式不必。"""
    script = START_CARD.read_text(encoding="utf-8")
    assert "--strict-mcp-config" in script
    # 锚在主分发的 case 上：refresh_settings 里也有同名的 case 分支
    blind_arm = re.search(r"^\s{4}blind\)\s+(mode_claude_clone.*)$", script, flags=re.MULTILINE)
    open_arm = re.search(r"^\s{4}open\)\s+(require_g1.*)$", script, flags=re.MULTILINE)
    assert blind_arm and blind_arm.group(1).rstrip().endswith("strict ;;"), "blind 分支没传 strict"
    assert open_arm and "strict" not in open_arm.group(1), "open 分支不该传 strict"
    packet = re.search(r"mode_packet\(\)(.*?)\n}", script, flags=re.DOTALL)
    assert packet and "--strict-mcp-config" in packet.group(1), "packet 的启动命令没带标志"


def test_isolation_checklist_has_the_mcp_check() -> None:
    text = (REPO / "scripts" / "verify-isolation.md").read_text(encoding="utf-8")
    assert "A11" in text and "mcp__" in text, "隔离清单缺 MCP 自证那一项"
    assert "--strict-mcp-config" in text


def test_committed_project_settings_keep_isolation() -> None:
    cfg = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert cfg["permissions"]["blockReadsOutsideWorkingDirectories"] is True
    assert cfg["sandbox"]["enabled"] is True
    assert cfg["sandbox"]["allowUnsandboxedCommands"] is False
    deny = cfg["permissions"]["deny"]
    assert any("git clone" in d for d in deny), "会话里不得 git clone（外部基准是 T01a 的事）"


# ---------- 启动脚本 ----------


def test_start_card_can_refresh_settings_of_an_existing_clone() -> None:
    """模板改了，已存在的 clone 不会自动更新；要有办法重新生成。"""
    script = START_CARD.read_text(encoding="utf-8")
    assert "--refresh-settings" in script


def test_start_card_is_executable_and_parses() -> None:
    assert START_CARD.is_file()
    assert START_CARD.stat().st_mode & 0o111, "start-card.sh 没有可执行位"
    subprocess.run(["bash", "-n", str(START_CARD)], check=True)


def test_start_card_refuses_unknown_id() -> None:
    r = subprocess.run(
        ["bash", str(START_CARD), "T99", "--dry-run"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode != 0
    assert "T99" in r.stderr


def test_start_card_refuses_open_mode_before_g1() -> None:
    """主仓库还没有 semantic-v1 时，普通模式必须被拒。G1 之后本测试自动跳过。"""
    has_tag = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "-q", "--verify", "refs/tags/semantic-v1"],
        capture_output=True, text=True,
    ).returncode == 0
    if has_tag:
        pytest.skip("semantic-v1 已存在，G1 已过")
    r = subprocess.run(
        ["bash", str(START_CARD), "T11", "--dry-run"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode != 0
    assert "G1" in r.stderr


def test_start_card_dry_run_touches_nothing(tmp_path) -> None:
    cards_dir = tmp_path / "cards"
    env_overrides = {"SEMDEBT_CARDS_DIR": str(cards_dir)}
    import os

    env = {**os.environ, **env_overrides}
    r = subprocess.run(
        ["bash", str(START_CARD), "T01", "--dry-run"],
        capture_output=True, text=True, cwd=REPO, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert not cards_dir.exists(), "--dry-run 不应该建任何目录"
    assert "git clone" in r.stdout and "[dry-run]" in r.stdout
