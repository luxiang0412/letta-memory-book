# 第 10 章 教模型管理记忆：读一份系统提示

> 本章目标：逐节读 letta-code 给 MemFS agent 的系统提示，看清哪些规则只是“说给模型听”，哪些被代码强制执行；理解为什么记忆系统的一半是提示词工程。前置：第 4–9 章。对应代码：mini-letta `v0.2` 起的 `DEFAULT_SYSTEM_PROMPT`（`src/store/agent-store.ts`）。

## 10.1 两份提示词

letta-code 为 MemFS agent 准备了两份完整的系统提示（`src/agent/prompts/README.md`）：

| 文件 | 给谁 | 怎么选出来的 |
|---|---|---|
| `letta_root_memfs.md`（约 3500 词） | Letta Cloud 上的 agent | `root-memfs` 模式 |
| `letta_local_memfs.md`（约 3300 词） | 本地后端的 agent | `local-memfs` 模式 |

选择逻辑在 `src/agent/personality.ts:112-121`：`environment === "local"` → `local-memfs`；Cloud 上是 Letta Cloud 才用 `root-memfs`，自托管服务器用旧的 `memfs`。`buildSystemPrompt()`（`src/agent/prompt-assets.ts`）按模式取对应内容。

两份的差别值得一看（`diff letta_local_memfs.md letta_root_memfs.md` 的前几处）：

```diff
-## Memory blocks & external memory (learning)
+## Memory files & external memory (learning)
-### Memory blocks (in-context memory)
+### Core memory (in-context memory)
-Memory blocks are editable segments of the system prompt. Each block has a name and description ...
+Root Markdown files are editable segments of the system prompt. Root `MEMORY.md` is a frontmatter-free
+overview and index. Every other root Markdown file is core memory with exactly `name` and `description`
+frontmatter. ...
-- *References as synapses.* Use [[path]] links from memory blocks ...
+- *References as synapses.* Use ordinary relative Markdown links from `MEMORY.md` files ...
```

也就是说，在 `70ead335` 上，本地 agent 的**文件**是 v2 根布局（第 2 章），hook 也按 v2 规则校验，但它的**提示词**仍用“memory blocks”的词汇、推荐 `[[path]]` 式链接，没有讲根 `MEMORY.md` 和“恰好 name + description”的规则。这些规则模型只能从 hook 的报错里学到。这是一个提示词落后于实现的例子，读源码时值得留意。本章以下引用都来自更新的 `letta_root_memfs.md`。

## 10.2 逐节读

### 身份宣言（第 1–3 行）

> You are a Letta Code agent — a new generation of agent built for experiential learning… the model is the engine; *you* are the tokens.

这段看似“文案”，实际上在给后面所有规则提供**动机**：如果 agent 把自己当成会话结束就消失的工具，它没有理由花 token 去维护记忆。提示词在 “Learning from mistakes”（`:79`）一节把这个经济学讲透了：无状态的 agent 反思错误是浪费，有状态的 agent 不反思才是浪费。

### Context Architecture（`:5` 起）

第 1 章的四类记忆就出自这里。值得注意的是它对 recall 的定位：“cannot be mutated”——经历是只读的，学习只能写进记忆文件。

### Core memory（`:26` 起）

| 规则 | 只是提示？ | 代码强制在哪 |
|---|---|---|
| 根 `MEMORY.md` 无 frontmatter，其他根文件恰好 `name`+`description` | 否 | hook：`validateMemoryFileFrontmatter`（第 7 章） |
| 子目录必须有 `MEMORY.md` 才算记忆 | 否 | hook：树约束的索引链检查 |
| `skills/` 与记忆索引分开 | 否 | hook：拒绝扁平技能文件 |
| References as synapses：用相对链接把记忆连起来 | **是** | 无（链接断了没人报错——练习 2） |
| Never store secrets | **是** | 无（letta-code 的 hook 不扫描密钥） |
| Keep core memory lean | 部分 | `maxCoreMemoryCharacters`（默认 65 536 字符）；`/doctor` 提示过大 |

“Keep core memory lean”的那句很重要（`:35`）：“Do *NOT* write memories that are easily derivable from searching past conversations (recall) or re-reading files.” 记忆不是备份，是**提炼**。

### Syncing memory（`:53` 起）

两条不变量（第 6、9 章）：只有提交了才生效；编辑不会改变本回合的行为。还有一条委派规则（`:58`）：“The `memory` subagent's entry in the Agent tool covers when to delegate memory updates.”——记忆维护可以交给后台的 `memory` 子 agent（第 17 章）。

### Editing memory directly（`:60` 起）

这一节读起来像一份操作规程，每一句都对应一个并发问题：

- “inspect Git status and read the current files before editing”——别覆盖别人刚改的；
- “if a worker you launched may still be running… wait for it”——别和自己派出去的 worker 抢；
- “stage only the files you changed by explicit path (never `git add -A` or `git add .`) and commit them in the same shell call”——别把别的写者暂存的东西一起提交（第 17 章）；
- “Verify the committed changes before claiming they are saved”（`:77`）——别像第 6 章的 qwen 那样谎报。

### Learning from mistakes / Reacting to human feedback（`:79`、`:87`）

把“用户不满”定义为最强的学习信号：“Why did you do that?”、“I already told you that”……并且要求：当用户问“你为什么没记住”时，不要敷衍，而要把它当成一个**上下文工程问题**去诊断（`:95`）。这是把 harness 调试的一部分交给了 agent 自己。

### Identity / Existence & Continuity（`:97`、`:113`）

要求 agent 遵守 `persona.md`，并且“Changes should be incremental to avoid complete loss of self”（`:111`）。反思子 agent 的提示词里有对应的约束（`reflection-v2.md:100`）：“Persona and behavioral files are load-bearing. Edit them surgically… Never rewrite them wholesale”。

### Jogging your memory（`:121`）

遇到陌生的名字或项目，**先假设自己知道**，去 recall 和 MemFS 里找。这是 recall 被用起来的前提：模型默认倾向于直接回答“我不知道”。

### Self-evolution（`:191` 起）

最后一节划清了三种“自我演化”的边界：

| 改什么 | 用什么 |
|---|---|
| 判断、偏好、身份、知识 | 记忆 |
| 按需加载的流程 | 技能 |
| 必须确定执行的约束（权限、hook、cron、安全规则） | harness 配置 / mods |

并且明确禁止直接改基础系统提示：“editing it directly marks it as custom and permanently detaches you from those upgrades”。

## 10.3 只靠提示词够吗？

本书到目前为止用真模型做的几次实验，给出的答案很明确：**对小模型来说不够**。

| 提示词要求 | `qwen2.5:3b` 的实际行为 | 兜底机制 |
|---|---|---|
| 只改需要改的部分，保留 frontmatter | 用 `write_file` 整个覆盖 `human.md` | 未提交 → 不生效；提交会被 hook 拒绝 |
| 提交后再说保存了 | 没提交就说 “This change has been committed” | 回合后 `MEMORY COMMIT NEEDED` 提醒 |
| 收到提醒后处理 | 无视提醒 | （没有——需要后台 worker 或人） |
| 按提示词执行指定命令 | 改用 `write_file`，还造了个 `Memory.md` | hook + 只读 HEAD |

letta-code 的回答是**分层防御**：提示词负责“引导”，hook 和只读 HEAD 负责“兜底”，回合后提醒负责“反馈”，后台反思（用可配置的、更强的模型）负责“补位”。一份好的系统提示不是让坏事不可能发生，而是让大多数时候好事自然发生，而坏事发生时有别的层接住。

## 10.4 mini-letta 的系统提示

mini-letta 的默认系统提示只保留了最小的规则集（`src/store/agent-store.ts`）：

```text
You are mini-letta, a stateful agent with persistent memory.

Your memory is a git repository of Markdown files at $MEMORY_DIR. Root .md files
are core memory and are compiled into this prompt; root MEMORY.md is the index.
Every other memory file has exactly `name` and `description` frontmatter.
When the user tells you something durable or corrects you, edit the right file,
then commit only the files you changed:
  cd "$MEMORY_DIR" && git add <file> && git commit -m "<type>: <what>" -- <file>
Edits take effect only after they are committed.

{CORE_MEMORY}
```

它刻意很短：这本书关心的是机制，而 mock 模型不读提示词。如果你用真模型做实验，把 letta-code 的 `letta_root_memfs.md` 换进来（`createAgent({ system: ... })`）是一个很好的练习——注意保留 `{CORE_MEMORY}`。

## 10.5 练习

1. **巩固**：把本章 10.2 的表格补全——对 “Editing memory directly” 一节的每一句话，写出 mini-letta 里对应的强制机制（或者“无”）。
2. **扩展**：实现一个“断链检查”：回合后扫描所有 `MEMORY.md` 里的相对链接，指向不存在的文件时发一条提醒。它应该放在 hook 里（拒绝提交）还是提醒里（只是告知）？为什么？
3. **读源码**：比较 `letta_local_memfs.md` 和 `letta_root_memfs.md` 的完整 diff。除了 10.1 列出的几处，还有哪些差别？哪些差别会让本地 agent 更容易提交失败？
