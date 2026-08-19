# GitHub Bulk Star

一次输入最多 6 个 GitHub 链接，预览并批量为仓库添加 Star 的 Codex Skill。

它适合处理两类链接：

- 仓库链接，例如 `https://github.com/openai/codex`：只处理这个仓库。
- 用户 repositories 页面，例如 `https://github.com/mollyhan-ai?tab=repositories`：只处理该用户公开仓库列表的第一页，不翻页。

普通用户主页（例如 `https://github.com/mollyhan-ai`）不会被直接执行。Skill 会先提出将其补充为 `?tab=repositories`，用户确认转换后才生成预览；转换确认不等于 Star 确认。

## 产品说明

GitHub Bulk Star 将多个 GitHub 链接解析为一份明确、去重的仓库清单。默认操作是只读预览，只有用户看到完整清单并再次明确确认后，才会使用当前登录的 GitHub 账号逐个添加 Star。

核心规则：

- 每批最多接收 6 个链接，仓库链接和 repositories 页面可以混合输入。
- repositories 页面只读取第 1 页，每个用户最多解析 30 个公开仓库。
- 独立仓库链接只贡献 1 个仓库。
- 重复仓库自动去重，已经 Star 的仓库自动跳过。
- 只增加 Star，永远不会取消 Star。
- 瞬时网络故障最多只对当前仓库重试 1 次，不会自动重跑整批。
- Issue、Pull Request、文件页面、非 GitHub 域名和其他深层链接都会被拒绝。

## 环境要求

- Python 3.9 或更新版本。
- 能够访问 GitHub API。
- 执行真实 Star 时，满足以下任一认证方式：
  - 已设置 `GH_TOKEN`；
  - 已设置 `GITHUB_TOKEN`；
  - 已安装 GitHub CLI，并完成 `gh auth login`。

令牌只用于当前 GitHub API 请求，Skill 不会打印或保存令牌。

## 安装到 Codex

使用 GitHub CLI 克隆到 Codex 的个人 Skills 目录：

```bash
gh repo clone mollyhan-ai/github-bulk-star ~/.codex/skills/github-bulk-star
```

如果目录已经存在，可以进入该目录并拉取更新：

```bash
cd ~/.codex/skills/github-bulk-star
git pull
```

安装后，在 Codex 中通过 `$github-bulk-star` 调用。

## 指令说明

### repositories 页面

```text
使用 $github-bulk-star 给以下 GitHub repositories 页面第一页的仓库 Star：
https://github.com/Nahzzz77?tab=repositories
https://github.com/liyongyan129-maker?tab=repositories
```

### 独立仓库

```text
使用 $github-bulk-star 给以下仓库 Star：
https://github.com/openai/codex
https://github.com/owner/project
```

### 混合输入

```text
使用 $github-bulk-star 处理以下链接：
https://github.com/owner-a?tab=repositories
https://github.com/owner-b/project-b
https://github.com/owner-c
```

第三个链接是普通用户主页。Skill 会先请求确认是否转换为：

```text
https://github.com/owner-c?tab=repositories
```

## 用户操作步骤

1. 准备最多 6 个 GitHub 链接。
2. 在 Codex 或兼容 Agent 中调用 `$github-bulk-star` 并粘贴链接。
3. 如果包含普通用户主页，先确认是否转换为 repositories 页面。
4. 查看 Skill 输出的完整仓库清单、总数和去重结果。此时不会改变任何 Star。
5. 确认目标无误后，回复类似：`确认 Star 以上 19 个仓库`。
6. 等待执行完成，查看新增、已跳过和失败数量。

在步骤 5 之前，不会发生 GitHub 写入。若仓库清单发生变化，必须重新预览并重新确认。

## 手动运行脚本

默认命令只生成预览：

```bash
python3 scripts/github_bulk_star.py \
  'https://github.com/owner?tab=repositories' \
  'https://github.com/owner/project'
```

在确认预览清单后执行真实 Star：

```bash
python3 scripts/github_bulk_star.py \
  --execute \
  --confirm STAR \
  'https://github.com/owner?tab=repositories' \
  'https://github.com/owner/project'
```

脚本要求 `--execute` 与 `--confirm STAR` 同时出现，避免误操作。

## 返回结果

执行完成后会报告：

- `Starred`：本次新增 Star 的仓库数。
- `already Starred`：此前已经 Star、因此跳过的仓库数。
- `failed`：未成功处理的仓库数及失败原因。

只要存在失败，脚本就会返回非零状态，并保留成功项目，不会自动取消或回滚 Star。

## 验证

运行自动化测试：

```bash
python3 -m unittest discover -s tests -v
```

项目包含链接解析、混合输入、去重、6 个链接上限、已有 Star 跳过和瞬时网络重试测试。

## 项目结构

```text
github-bulk-star/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── scripts/github_bulk_star.py
└── tests/test_github_bulk_star.py
```
