# 第 0 章 本书怎么读

> 本章目标：知道这本书要带你做成什么、怎么准备环境、怎么对照着源码读。前置：会写 TypeScript，会用 git。对应代码：`code/mini-letta`（tag `v0.1`～`v1.0`）。

## 0.1 这本书要解决什么问题

几乎每个用过 coding agent 的人都遇到过同一件事：你在上午告诉它“我们用 pnpm，不要用 npm”，下午开一个新会话，它又敲出了 `npm install`。

模型本身不记事。它在每一次调用里看到的，只有这一次请求里塞进去的 token。所谓“记忆”，是 **harness（模型外面那层程序）** 替它保存、整理，并在下一次调用时重新塞回上下文里的东西。

[Letta Code](https://github.com/letta-ai/letta-code) 是把这件事做得最彻底的开源 harness 之一。它的系统提示里有一句话概括了整个设计哲学：

> the model is the engine; *you* are the tokens.（模型只是引擎；*你*是那些 token。）
> —— `src/agent/prompts/letta_root_memfs.md:3`

这本书只讲 letta-code 的**记忆子系统**：

- 记忆存在哪里？——一个 git 仓库，里面是 Markdown 文件（MemFS）；
- 记忆怎么进入模型？——每次对话开始时把**已提交**的记忆“编译”进系统提示；
- 上下文满了怎么办？——压缩（compaction），但原始消息永远可以被检索（recall）；
- 谁来整理记忆？——除了 agent 自己，还有对话结束后在后台运行的“反思”（reflection / sleeptime）子 agent；
- 多台机器、多个 agent 同时写怎么办？——git 同步、worktree 隔离、锁、内核级沙箱。

**读完这本书，你能从零写出一个带长期记忆的 agent**：它的记忆是 git 里的 Markdown，会被编译进系统提示，长对话会自动压缩并能找回被压掉的细节，空闲时会有后台子 agent 帮它整理记忆，记忆还能在机器之间同步。这个 agent 就是本书的配套项目 **mini-letta**。

## 0.2 配套项目 mini-letta

mini-letta 用 **Bun + TypeScript** 写成（和 letta-code 同一套技术栈，只是降了一档：没有 Ink 终端 UI，用 readline；没有云端，用本地 bare 仓库扮演服务器）。它是一个独立的 git 仓库，每个 Part 结束打一个 tag，每个 tag 都能跑、测试都是绿的：

| 版本 | 能力 | 对应章节 |
|---|---|---|
| `v0.1` | 最小 agent loop、mock LLM、两个记忆块拼进系统提示 | 第 1–3 章，Lab 1 |
| `v0.2` | MemFS：每个 agent 一个 git 记忆仓库、v2 布局、文件/bash 工具、pre-commit 校验 | 第 4–7 章，Lab 2 |
| `v0.3` | 系统提示编译器、按对话缓存、对话中途的 `<memory_update>`、回合后提醒 | 第 8–10 章，Lab 3 |
| `v0.4` | token 预算、滑动窗口压缩、上下文 id 列表、BM25 recall 搜索 | 第 11–13 章，Lab 4 |
| `v0.5` | 后台反思：水位线、触发器、worktree 隔离、合并状态机、锁 | 第 14–17 章，Lab 5 |
| `v1.0` | 远端同步、跨 agent 隔离（路径守卫 + bwrap）、Memory Palace 网页、端到端脚本、Docker | 第 18–20 章，Lab 6 |

想看某一章到底加了什么代码，直接：

```bash
cd code/mini-letta
git diff v0.2 v0.3 --stat
git diff v0.2 v0.3 -- src/agent/system-prompt.ts
```

## 0.3 准备环境

你需要：

- **Bun ≥ 1.3**（本书用 1.3.11 验证）；
- **git ≥ 2.24**（本书用 2.43）；
- 可选：**Ollama**，用来跑一次真模型（本书用 `qwen2.5:3b`）；
- 可选：Linux 上的 **bubblewrap**（`bwrap`），第 19 章的内核沙箱要用；
- 可选：Docker，Lab 6 的部署要用。

```bash
cd code/mini-letta
bun install
bun test                         # 50 个测试，全部离线
export MINI_LETTA_HOME=$(mktemp -d)   # 永远在临时目录里玩，别污染真实状态
bun src/cli.ts chat -p "记住：我用 pnpm"
```

`MINI_LETTA_HOME` 对应 letta-code 的 `LETTA_LOCAL_BACKEND_DIR`。letta-code 的 CLAUDE.md 专门提醒过：手动试本地后端时“set `LETTA_LOCAL_BACKEND_DIR` to a temporary directory first. Otherwise the run reads and mutates your real `~/.letta/lc-local-backend`”。我们照做。

**为什么默认用 mock 模型？** 记忆系统的大部分逻辑（git、编译、压缩、合并）和模型聪不聪明无关。一个确定性的 mock 模型让每一章的输出都可复现、每个测试都稳定。但我们也会在关键处换上真模型——而真模型（尤其是小模型）会以各种方式“不守规矩”：声称提交了其实没提交、只说“我现在去读文件”然后就结束了……这些都是本书里**真实观察到的**行为，它们直接推动了 mini-letta 里好几处防御设计。

## 0.4 怎么读 letta-code 源码

本书引用的源码都来自 **letta-ai/letta-code @ `70ead335`**。引用格式是 `路径:行号`，例如 `src/backend/local/system-prompt-compilation.ts:432`。所有行号都在这个 commit 上用 `grep -n` 核对过。

letta-code 很大（`src/` 下几千个文件），读之前先建立三个认识：

**1. 分层。** letta-code 的 CLAUDE.md 定义了严格的层次（`cli/ → websocket/ → agent/ → tools/ → backend/ → …→ utils/`），只允许向下依赖。记忆相关的代码主要在三处：

| 目录 | 放了什么 |
|---|---|
| `src/agent/memory-*.ts` | MemFS 的 git 操作、格式规则、worktree、锁、冲突修复 |
| `src/backend/local/` | 本地后端：系统提示编译、压缩、transcript 搜索 |
| `src/cli/helpers/reflection-*.ts`、`memory-reminder.ts` | 反思的触发、transcript 切片、启动与收尾 |

**2. 三条编排路径。** 交互式 TUI（`src/cli/app/`）、headless（`src/headless.ts`）、websocket 监听器（`src/websocket/listener/`）各有一套回合编排代码。同一个“回合结束后同步记忆”的动作，在三处分别被调用（见第 3 章）。本书主要沿 headless 和本地后端读，因为它们最直接。

**3. 两种后端。** Cloud（Letta 服务器保存 agent，记忆仓库托管在服务器上）和 Local（`LETTA_LOCAL_BACKEND_EXPERIMENTAL=1`，一切都在本机）。本书主要读 **Local** 后端：它把服务器端做的事（比如系统提示编译）也搬到了本地，读起来是一个完整闭环。

如果你想在本机跑 letta-code 的测试或小实验，建议像本书这样**克隆一份到临时目录再 `bun install`**，不要在你正在开发的工作区里装依赖。另外注意：letta-code 的测试预加载脚本会把 `HOME` 换成临时目录（`scripts/test-home-preload.ts:48`），这意味着你的全局 git 配置在测试里**不生效**——第 16 章会讲到这件事怎么让我们误判过一次。

## 0.5 每章的结构

每章大致是：

1. **问题与概念**——为什么需要它；
2. **letta-code 是怎么做的**——按调用顺序读源码，带行号和不超过 20 行的摘录；
3. **自己实现一遍**——mini-letta 的关键代码，以及“省略了什么、为什么”；
4. **运行与验证**——精确的命令和**真实**输出；
5. **练习**——一道巩固、一道扩展、一道读源码；
6. **延伸阅读**。

关于诚实：书里的“踩坑记录”只写真的踩到的坑；凡是输出，都是实际运行得到的；凡是对 letta-code 行为的断言，要么有源码行号，要么有我们跑过的探针实验，要么明确标注“未验证”。

## 0.6 阅读路线

- **只想理解思想**：第 1、3、9、15、16 章。
- **想自己实现一个**：按顺序读，每个 Lab 都动手。
- **在给 letta-code 贡献代码**：重点看第 9 章（`<memory_update>` 的生命周期）和第 16 章（全局 `core.autocrlf` 与反思 worktree），这两处我们用探针在 `70ead335` 上观察到了值得注意的行为；第 15 章的“空反思被当成成功”是在 mini-letta 里用真模型踩到的，letta-code 是否有同样的问题我们**没有验证**，章里给出了该去看的代码位置。

下一章，我们从最根本的问题开始：agent 为什么需要记忆，以及“记忆”到底分几种。
