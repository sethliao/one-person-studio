# 更新日志

> 本项目版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`。
> 发版时 `VERSION` / `CHANGELOG.md` / GitHub Release **三对齐**（规范见 skill `repo-conventions`）。

## [0.7.2] - 2026-10-09

### Added

- **自动发版**：新增 `.github/workflows/release.yml` —— 以后**推 `v*` tag 就自动建 Release**，
  说明文字优先取 `CHANGELOG.md` 的对应版本段（取不到则退回 GitHub 自动生成）。
- 发版流程就此收敛成三步：改 `VERSION` → 补 `CHANGELOG.md` → `git tag vX.Y.Z && git push --tags`。
  （Release 页面不再需要手动点 —— 推 tag 前 GitHub 不会自动建条目，这是加这条 workflow 的原因。）

## [0.7.1] - 2026-10-09

### Fixed

- **修 vault 改名遗留的坏路径**：`hermes_vault_clean` → `ob_vault_s`（24 处，跨 15 个文件）
  - 背景：知识库已于 2026-10-05 改名 `ob_vault_s`，但当时只改了 md 叙述与 `obsidian://` URI，
    **漏掉了 skill 里的命令与脚本绝对路径**。
  - 症状：旧路径不存在，命令**静默失败**（`No such file`），不报错但什么都没跑成。
  - 受影响：`agnes-video-prompt` · `x-bookmarks-mining` · `design-codex` · `behance-case-deck` ·
    `ep-qa` · `drama-claw-hermes` · `social-media-archive` · `new-tool-triage` ·
    `ai-handover-pack` · `content-research-board` · `agent-skills-bridge`

### Changed

- **拔出全部本机绝对路径，改用占位符 `$VAULT_PATH`**（17 个文件）
  - 库内文件路径一律写成 `$VAULT_PATH/...`；安装者 `export VAULT_PATH="$HOME/Documents/your-vault"` 即可，
    或装完后全局替换 —— README 与 README.en.md 均已加配置章节。
  - 脚本侧配套：`ai-handover-pack` 读 JSON 的 `src` 改为先 `os.path.expandvars()` 再 `expanduser()`，
    让占位符**真能展开**（原来只有 `expanduser()`，`$VAR` 不会被解析）。
  - 候选列表式路径（`content-research-board` 的 `analyze_collections` / `verify_board`）无需改动 ——
    找不到会自动 fallback 到下一个候选，不会崩。

### Note

- 用户名级绝对路径（`/Users/<name>/...`）**已从本仓彻底清除**；
  其余本机路径（Python 解释器、`~/Code/…`）统一用 `~/` 开头，随 HOME 生效。
