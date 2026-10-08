# 从 Letta Code 到 Mini-Letta：给 Agent 装上会成长的记忆

> 读 [letta-ai/letta-code](https://github.com/letta-ai/letta-code)（`70ead335`）记忆子系统的源码，从零写一个带 **git 记忆、系统提示编译、上下文压缩、后台反思、多机同步与隔离** 的 agent。
> 配套代码：本仓库的 `code/mini-letta` 目录（独立的 git 仓库；Bun + TypeScript，`v0.1` → `v1.0`，每个 Part 一个 tag）。

**读完这本书，你能从零写出一个带长期记忆的 agent**：它的记忆是 git 仓库里的 Markdown 文件，只有已提交的记忆会被编译进系统提示；对话中途的记忆变化以 `<memory_update>` 告知模型而不破坏提示缓存；长对话会在溢出前自动压缩，被压掉的细节能用 recall 找回；对话之后，一个反思子 agent 在隔离的 git worktree 里整理记忆，再由一个六状态的收尾状态机合并回来；记忆能在多台机器之间同步，同一台机器上的其他 agent 看不到它。

## 目录

**Part 0 导读**
- [第 0 章 本书怎么读](./chapters/00-how-to-read.md)

**Part I 全景**
- [第 1 章 Agent 为什么需要记忆](./chapters/01-why-memory.md)
- [第 2 章 letta-code 记忆子系统地图](./chapters/02-memory-map.md)
- [第 3 章 ★ 一条记忆的一生](./chapters/03-life-of-a-memory.md)
- [Lab 1 mini-letta v0.1：能对话、记忆块进系统提示](./chapters/lab-1-minimal-agent.md)

**Part II 记忆即文件：MemFS**
- [第 4 章 从 memory block 到 memory file](./chapters/04-blocks-to-files.md)
- [第 5 章 MemFS v2 布局：常驻、按需与技能](./chapters/05-memfs-v2-layout.md)
- [第 6 章 用 git 管记忆](./chapters/06-git-as-memory.md)
- [第 7 章 守门员：pre-commit hook、frontmatter 与预算](./chapters/07-gatekeepers.md)
- [Lab 2 mini-letta v0.2：记忆变成 git 仓库](./chapters/lab-2-memfs.md)

**Part III 编译：从记忆到系统提示**
- [第 8 章 ★★ 系统提示编译器](./chapters/08-prompt-compiler.md)
- [第 9 章 ★★ 何时重编译：缓存、`<memory_update>` 与提醒](./chapters/09-when-to-recompile.md)
- [第 10 章 教模型管理记忆：读一份系统提示](./chapters/10-teaching-memory.md)
- [Lab 3 mini-letta v0.3：会成长的人格](./chapters/lab-3-living-persona.md)

**Part IV 上下文窗口与 recall**
- [第 11 章 上下文预算：估算、阈值与“地板”](./chapters/11-context-budget.md)
- [第 12 章 压缩：滑动窗口、摘要与上下文 id 列表](./chapters/12-compaction.md)
- [第 13 章 Recall：找回被压缩掉的经历](./chapters/13-recall.md)
- [Lab 4 mini-letta v0.4：长对话不撑爆，也不失忆](./chapters/lab-4-long-conversations.md)

**Part V 睡眠时间：后台反思**
- [第 14 章 ★★ 睡眠时间：反思什么时候发生](./chapters/14-reflection-triggers.md)
- [第 15 章 ★★ 反思子 agent：读经历、写记忆](./chapters/15-reflection-subagent.md)
- [第 16 章 ★★ worktree 隔离与合并状态机](./chapters/16-worktree-merge.md)
- [第 17 章 并发写者：锁、worker 与冲突修复](./chapters/17-concurrent-writers.md)
- [Lab 5 mini-letta v0.5：对话结束，后台反思](./chapters/lab-5-sleeptime.md)

**Part VI 平台化**
- [第 18 章 同步与多机：记忆跟着 agent 走](./chapters/18-sync.md)
- [第 19 章 记忆安全：跨 agent 隔离、沙箱与密钥](./chapters/19-isolation.md)
- [第 20 章 观察与调试记忆：Memory Palace、/doctor 与审计](./chapters/20-observability.md)
- [Lab 6 mini-letta v1.0：多机同步、隔离、Palace 与部署](./chapters/lab-6-palace.md)

**附录**
- [附录 A 源码地图](./appendix/a-source-map.md)
- [附录 B 术语表](./appendix/b-glossary.md)
- [附录 C 横向对比：几种 agent 记忆的设计](./appendix/c-comparison.md)
- [附录 D 练习参考答案](./appendix/d-answers.md)

## 快速开始

```bash
cd code/mini-letta
bun install
bun test                                   # 50 个测试，离线
export MINI_LETTA_HOME=$(mktemp -d)        # 永远在临时目录里玩
bun src/cli.ts chat -p "记住：我用 pnpm"
bun src/cli.ts chat -c another -p "你知道我什么？"
bun scripts/demo.ts && bun src/cli.ts palace   # 看 Memory Palace
git diff v0.2 v0.3                         # 看某一章加了什么
```

## 这本书是怎么验证的

- **代码**：mini-letta 每个 tag 都在独立 worktree 里重新跑过测试和类型检查：`v0.1` 4 个、`v0.2` 8 个、`v0.3` 15 个、`v0.4` 21 个、`v0.5` 34 个、`v1.0` 50 个，全部通过；madge 检查无循环依赖。
- **真模型**：在本地 Ollama（`qwen2.5:3b`）上跑过 v0.1–v0.5 的关键流程。小模型的失误（谎称已提交、覆盖文件、空反思、只说不做、摘要超长）都原样记录在相应章节，并推动了 mini-letta 里的防御设计。
- **对照 letta-code**：所有 `path:line` 都在 `70ead335` 上用 `grep -n` 核对过。在一个本地克隆里做了三次探针：`<memory_update>` 的生命周期（第 3、9 章）、全局 `core.autocrlf` 对反思 worktree 的影响（第 16 章）、以及**同一个记忆仓库上 letta-code 与 mini-letta 两个编译器的输出逐字节一致**（第 8 章）。
- **对照中修掉的缺口**：写书过程中 `v1.0` tag 移动过四次，修复了 `--no-verify` 绕过 hook、回合之间的提交未被审计、frontmatter 解析与 letta-code 不一致、小窗口下反思永远失败等问题，故事都写在了正文里。
- **界面与部署**：Memory Palace 用 headless Chrome 截图（含 390px 窄屏检查）；`docker compose` 部署后，端到端脚本对运行中的服务跑通了 10 个检查点。

## 已知局限

- mini-letta 只实现 MemFS v2；反思子 agent 在同一进程内运行（letta-code 是独立进程）；没有 memory worker、冲突修复 worker、反思重试退避、多对话反思。
- 内核沙箱只实现了 Linux bubblewrap；Docker 镜像内不可用时自动降级。
- 真模型验证只用了一个 3B 小模型；它暴露了很多问题，但不代表更强模型的表现。

> 本书基于 letta-code 的公开源码写成，与 Letta 官方无关。
