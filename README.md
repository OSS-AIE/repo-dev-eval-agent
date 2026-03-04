# OSS Issue Fixer Agent

一个面向 `pytorch/vllm/sglang/triton` 等开源社区的自动修复与提 PR agent。

## 能力

- 社区仓库可配置（`config/repos.yaml`）。
- 自动抓取 issue/feature，按仓库规则生成分支、commit、PR 标题。
- 严格质量门禁：仅在本地校验命令全部通过后才提交 PR。
- 支持每日 PR 配额（默认 `10`）。
- 支持从仓库 `CONTRIBUTING.md` 拉取规范作为提示上下文。

## 快速开始

```bash
cd D:\vbox\repos\oss-issue-fixer-agent
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

配置环境变量（建议用系统环境变量，不要写入代码）：

- `GITHUB_TOKEN`
- `OPENAI_API_KEY`（可选，用于 LLM patch 生成）
- `OPENAI_BASE_URL`（可选）
- `OPENAI_MODEL`（可选）

运行一次：

```bash
oss-fixer run-once --config config/repos.yaml --max-prs 10
```

每日调度：

```bash
oss-fixer run-daily --config config/repos.yaml
```

## 设计说明

1. 每个仓库单独定义：
   - issue 标签筛选
   - PR 标题模板（如 `[Bugfix] {title}`）
   - commit 模板
   - 质量门禁命令（lint/test/build）
   - fix 命令（可接入你自己的自动修复器）
2. Agent 只在 `git diff` 非空且质量门禁全通过时 commit/push/PR。
3. 自动 fork 目标仓库，PR 从你的 fork 提交到 upstream。

## 重要提示

- “每天至少 10 个 PR”可以通过配额调度实现，但是否真正成功取决于：
  - issue 可修复性
  - CI 资源与测试时长
  - 社区审核规则
- 建议先 `--dry-run` 跑 1~2 天观察稳定性，再切正式模式。
