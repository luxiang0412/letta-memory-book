# Lab 3 mini-letta v0.3：会成长的人格

> 目标：系统提示编译器（含 `<deferred-memory>`）、按对话缓存、持久化的 `<memory_update>`、agent-info 与 `MEMORY COMMIT NEEDED` 提醒。演示：agent 修改自己的 persona，同一对话的下一回合就体现出来，系统提示却一个字节都没变。前置：第 8–10 章。完成后：`git checkout v0.3`。

## L3.1 改动一览

```text
$ git diff v0.2 v0.3 --stat
 package.json                    |   2 +-
 src/agent/loop.ts               |  57 +++++++++++------
 src/agent/reminders.ts          |  80 ++++++++++++++++++++++++
 src/agent/system-prompt.ts      |  59 ++++++++++++++++++
 src/cli.ts                      |  24 ++++---
 src/llm/mock.ts                 |  58 +++++++++++++++--
 src/memory/compile.ts           |  96 +++++++++++++++++-----------
 src/store/conversation-store.ts |  17 ++++-
 test/v02-memfs.test.ts          |   6 +-
 test/v03-compile.test.ts        | 135 ++++++++++++++++++++++++++++++++++++++++
 10 files changed, 457 insertions(+), 77 deletions(-)
```

## L3.2 步骤

**1. 编译器**（`src/memory/compile.ts`，第 8 章）。`readCommittedMemory` + `renderCoreMemory`，返回 `{content, coreMemory, compiledAt, rawSystemHash, memfsRevision}`。去掉 `<memory_metadata>`。

**2. 对话级状态文件**。`ConversationStore` 加上 `readJson/writeJson/removeJson`，后面的缓存、提醒、压缩、反思都用它在对话目录里存小 JSON。

**3. 缓存**（`src/agent/system-prompt.ts`，第 9 章）。`resolveSystemPrompt` 的三分支；`invalidateSystemPrompt` 删除缓存，下一步就会完整编译（对应 letta-code 的 `/recompile`）。

**4. 提醒**（`src/agent/reminders.ts`）。`wrapReminder` / `stripReminders` / `isReminderOnly`；`formatMemoryUpdate`、`formatAgentInfo`、`checkMemoryAfterTurn`；`enqueueReminder` / `drainReminders` 用 `pending-reminders.json` 做队列。

**5. 循环**（`src/agent/loop.ts`）。回合开始：取出待发提醒，首条消息前加 agent-info，拼成一条 user 消息。每一步：`resolveSystemPrompt`，有 `memoryUpdate` 就先追加一条提醒消息。回合结束：`checkMemoryAfterTurn`，脏就入队。

**6. mock 学会“读记忆”**。三处改动：

- `lastMessage()` / `lastUserText()` 跳过只有提醒的 user 消息、去掉提醒部分——否则模型会去“回答”提醒；
- `currentMemorySection()`：最新的 `<memory_update>` 优先于系统提示；
- 新规则“设定：X”改 `persona.md`；如果当前 persona 里有“回答末尾总是加上 X”，所有最终回复都加上 X——**行为由记忆驱动**，这让我们能在测试里直接观察记忆是否生效。

## L3.3 运行

```bash
bun test test/v03-compile.test.ts
export MINI_LETTA_HOME=$(mktemp -d)
bun src/cli.ts chat -p "你好"
bun src/cli.ts chat -p "设定：回答末尾总是加上 🦉"
bun src/cli.ts chat -p "你好"
bun src/cli.ts chat -p "再说一次"
bun src/cli.ts prompt | grep -c "🦉"
bun src/cli.ts prompt --fresh | grep "🦉"
bun src/cli.ts memory log
```

实际输出：

```text
（mock）我听到了：你好

  ⚙ bash({"command":"cd \"$MEMORY_DIR\" && printf '%s\\n' '- 回答末尾总是加上 🦉' >> persona.md && git add persona.md && git commit -q -m 'feat: update persona' -- persona.md && git log --oneline -1"})
  ✓ ab85f70 feat: update persona

  ↻ memory changed — injected <memory_update> reminder
好的，我已经把这件事记进记忆里了。 🦉
（mock）我听到了：你好 🦉
（mock）我听到了：再说一次 🦉
[cached · compiled 2026-10-08T15:55:21.450Z · memfs ab85f70]
0
[fresh · compiled 2026-10-08T15:55:21.550Z · memfs ab85f70]
- 回答末尾总是加上 🦉
ab85f70 (HEAD -> main) feat: update persona
ad9f5f9 chore: initialize local memory
```

看一眼对话目录，理解每个文件：

```bash
D=$MINI_LETTA_HOME/agents/agent-default/conversations/default
ls $D                                  # messages.jsonl  pending-reminders.json  system-prompt.json
jq -r '.memfsRevision[0:7], .compiledAt' $D/system-prompt.json
grep -c '<memory_update>' $D/messages.jsonl
```

## L3.4 一个后来变成测试的小实验

把 `persona.md` 改坏（删掉 frontmatter），用 `git commit --no-verify` 绕过 hook，再聊一句：

```text
$ bun src/cli.ts chat -p "你好" >/dev/null
$ D=$(bun src/cli.ts memory path)
$ printf 'BROKEN persona without frontmatter\n' > $D/persona.md && git -C $D commit -q --no-verify -am broken
$ bun src/cli.ts chat -p "在吗"
  ↻ memory changed — injected <memory_update> reminder
（mock）我听到了：在吗
$ grep -o 'BROKEN persona without frontmatter' .../conversations/default/messages.jsonl
BROKEN persona without frontmatter
```

坏内容随着 `<memory_update>` 进入了对话。更糟的是，我们当时（v1.0 的第一版）以为已经有了审计——但这次提交发生在**两个回合之间**，而审计只看“本回合内 HEAD 有没有动”，于是一条 `MEMORY INVALID` 都没有。这个实验直接变成了一个回归测试和一次修复（第 7 章 7.9）：现在每个新的 HEAD 都会在回合开始和结束时被审计一次。

## L3.5 练习

1. **巩固**：写一个测试：原始系统提示变了（`agent.system` 改了一个字），下一步应该完整重编译，并且**不**产生 `<memory_update>`。
2. **扩展**：给 CLI 加 `--show-reminders`，在每回合开始时打印本回合带上的提醒。
3. **读源码**：letta-code 的 agent-info 提醒（`src/cli/helpers/agent-info.ts` 的 `buildAgentInfo`）在什么条件下显示记忆目录？为什么不是所有 agent 都显示？
