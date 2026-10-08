# 《从 Letta Code 到 Mini-Letta：给 Agent 装上会成长的记忆》大纲

> 参照仓库：letta-ai/letta-code @ `70ead335`（只讲记忆子系统）
> 读者目标：读完能从零写出一个**带长期记忆**的 coding agent——记忆是 git 仓库里的 Markdown 文件，会被编译进系统提示，上下文满了会压缩，空闲时由后台“反思”子 agent 整理记忆。
> 写作方式：每章先读真源码（`path:line`），再在 mini-letta 里重写一遍；每个 Part 以一个 Lab 收尾，打一个 git tag。

## 贯穿全书的项目：mini-letta（TypeScript + Bun）

| 版本 | 能力 | 章节 |
|---|---|---|
| v0.1 | 最小 agent loop（CLI）、mock LLM、两个静态记忆块拼进系统提示 | 1–3, Lab 1 |
| v0.2 | MemFS：每个 agent 一个 git 记忆仓库、v2 布局、文件工具、pre-commit 校验 | 4–7, Lab 2 |
| v0.3 | 系统提示编译器、revision 缓存、对话中途 `<memory_update>` | 8–10, Lab 3 |
| v0.4 | token 预算、滑动窗口压缩、transcript 持久化与 recall 搜索 | 11–13, Lab 4 |
| v0.5 | 后台反思：触发器、transcript 切片、worktree 隔离、合并状态机、写锁 | 14–17, Lab 5 |
| v1.0 | 远端同步、多 agent 隔离、Memory Palace 网页查看器、端到端脚本 | 18–20, Lab 6 |

技术栈：Bun + TypeScript、系统 `git`、readline CLI（替代 Ink TUI）、`Bun.serve` 做 Palace 页面；
LLM 用确定性 **mock provider**（离线可跑，会发工具调用），另用 OpenAI 兼容接口对接本地 Ollama 做一次真模型验证。

## Part 0 导读
- [第 0 章 本书怎么读](./chapters/00-how-to-read.md)

## Part I 全景（浅）
- [第 1 章 Agent 为什么需要记忆](./chapters/01-why-memory.md)
- [第 2 章 letta-code 记忆子系统地图](./chapters/02-memory-map.md)
- [第 3 章 ★ 一条记忆的一生](./chapters/03-life-of-a-memory.md)
- [Lab 1 mini-letta v0.1：能对话、记忆块进系统提示](./chapters/lab-1-minimal-agent.md)

## Part II 记忆即文件：MemFS
- [第 4 章 从 memory block 到 memory file](./chapters/04-blocks-to-files.md)
- [第 5 章 MemFS v2 布局：常驻、按需与技能](./chapters/05-memfs-v2-layout.md)
- [第 6 章 用 git 管记忆](./chapters/06-git-as-memory.md)
- [第 7 章 守门员：pre-commit hook、frontmatter 与预算](./chapters/07-gatekeepers.md)
- [Lab 2 mini-letta v0.2：记忆变成 git 仓库](./chapters/lab-2-memfs.md)

## Part III 编译：从记忆到系统提示 ★★
- [第 8 章 ★★ 系统提示编译器](./chapters/08-prompt-compiler.md)
- [第 9 章 ★★ 何时重编译：缓存、`<memory_update>` 与提醒](./chapters/09-when-to-recompile.md)
- [第 10 章 教模型管理记忆：读一份系统提示](./chapters/10-teaching-memory.md)
- [Lab 3 mini-letta v0.3：会成长的人格](./chapters/lab-3-living-persona.md)

## Part IV 上下文窗口与 recall
- [第 11 章 上下文预算：估算、阈值与“地板”](./chapters/11-context-budget.md)
- [第 12 章 压缩：滑动窗口、摘要与上下文 id 列表](./chapters/12-compaction.md)
- [第 13 章 Recall：找回被压缩掉的经历](./chapters/13-recall.md)
- [Lab 4 mini-letta v0.4：长对话不撑爆，也不失忆](./chapters/lab-4-long-conversations.md)

## Part V 睡眠时间：后台反思 ★★
- [第 14 章 ★★ 睡眠时间：反思什么时候发生](./chapters/14-reflection-triggers.md)
- [第 15 章 ★★ 反思子 agent：读经历、写记忆](./chapters/15-reflection-subagent.md)
- [第 16 章 ★★ worktree 隔离与合并状态机](./chapters/16-worktree-merge.md)
- [第 17 章 并发写者：锁、worker 与冲突修复](./chapters/17-concurrent-writers.md)
- [Lab 5 mini-letta v0.5：对话结束，后台反思](./chapters/lab-5-sleeptime.md)

## Part VI 平台化（深）
- [第 18 章 同步与多机：记忆跟着 agent 走](./chapters/18-sync.md)
- [第 19 章 记忆安全：跨 agent 隔离、沙箱与密钥](./chapters/19-isolation.md)
- [第 20 章 观察与调试记忆：Memory Palace、/doctor 与审计](./chapters/20-observability.md)
- [Lab 6 mini-letta v1.0：多机同步、隔离、Palace 与部署](./chapters/lab-6-palace.md)

## 附录
- [A 源码地图（概念 → 路径）](./appendix/a-source-map.md)
- [B 术语表](./appendix/b-glossary.md)
- [C 横向对比：Letta 服务器 / 抽取式记忆 / 通用存储 / Claude Code 项目记忆](./appendix/c-comparison.md)
- [D 练习参考答案](./appendix/d-answers.md)
