# 第 13 章 Recall：找回被压缩掉的经历

> 本章目标：理解 recall 记忆的三件事——全部历史永久保存、可检索、检索者如何避开自己制造的噪声；实现一个带中文分词与 BM25 的检索工具，并修掉两个真实踩到的排序 bug。前置：第 12 章。对应代码：mini-letta `v0.4` `src/recall/search.ts`、`src/tools/recall-tool.ts`。

## 13.1 压缩之后，细节去哪了

第 12 章的 mock 摘要器只记住每句话的前 12 个字。“我们的数据库端口是 5433，别用默认的 5432”被压缩成了“我们的数据库端口是 5”。几十回合之后用户问：“还记得数据库端口吗？”

这时有三种可能的回答：

1. 编一个（最糟）；
2. “我不记得了”（诚实但没用）；
3. 去翻原始记录（recall）。

letta-code 的系统提示用两段话推动模型选第三种：一是 Context Architecture 里“Use the recall subagent to search through past experience whenever you are missing context from the past”（`letta_root_memfs.md:14`）；二是 “Jogging your memory”（`:121`）：遇到陌生的名字、项目，不要假设自己不知道，先去 recall 和 MemFS 里找。

## 13.2 letta-code 的 recall：一个分叉出来的子 agent

```markdown
<!-- src/agent/subagents/builtin/recall.md -->
---
name: recall
description: Recall past interactions and experience
tools: Bash, Read
model: inherit
fork: true
---
```

`fork: true`：recall 子 agent **继承父对话的全部历史**（会话分叉），所以它知道父 agent 在找什么。它不用专门的检索工具，而是用 Bash 调 CLI：

```bash
letta messages search --query "topic keywords" --limit 5          # 找到针
letta messages list --before "message-xyz" --limit 10             # 向前展开上下文
letta messages list --after "message-xyz" --order asc --limit 10  # 向后展开
```

这套“针 + 展开”的策略写在 `src/agent/prompts/recall_subagent_local.md` 里，此外还有按日期范围检索、换同义词等策略。把检索放进子 agent 的好处是：检索过程中翻出来的大量消息不进入父 agent 的上下文，父 agent 只拿到最后的结论（输出格式要求：直接回答、关键发现、何时讨论、结论）。

## 13.3 本地检索的实现：`searchLocalTranscriptMessages`

本地后端的检索在 `src/backend/local/transcript-search.ts:523`。三个值得学的点：

**(1) 中日韩文字的分词。** 中文没有空格，按 `[\p{L}\p{N}]+` 切出来的“词”可能是一整句话。letta-code 的做法是把一个混合串拆成“CJK 段”和“非 CJK 段”，再在 CJK 段上做**子串匹配**：

```ts
// src/backend/local/transcript-search.ts:229-252（节选）
function tokenize(value: string): string[] {
  const words = value.normalize("NFKC").toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  return words.flatMap((word) => {
    if (CJK_RUN.test(word) || !CJK_CHARACTER.test(word)) return [word];
    // 混合词：在 CJK / 非 CJK 的边界处切开
    ...
  });
}

// :258-268
function termFrequency(tokens: readonly string[], term: string): number {
  if (CJK_RUN.test(term)) {
    // These scripts commonly omit word separators. Preserve substring recall
    // within a run without restoring Latin token-suffix matches.
    return tokens.reduce((count, token) => count + token.split(term).length - 1, 0);
  }
  return tokens.reduce((count, token) => count + Number(token === term), 0);
}
```

“数据库端口”能在“我们的数据库端口是”这个 CJK 段里被找到；而英文仍然整词匹配，`port` 不会命中 `export`。

**(2) BM25 排序**（`rankMatches()`，`:317`），参数 `k1 = 1.2`、`b = 0.75`，再加上引号短语的强制过滤和加分。

**(3) 降权“检索回声”。** 每次检索都会在历史里留下痕迹：一条调用检索的 assistant 消息、一条检索结果。下一次检索时，这些痕迹和真正的原始讨论争抢排名。letta-code 把它们的分数乘以 0.1（`:368`）。还有一个更微妙的回声：

```ts
// src/backend/local/transcript-search.ts:570-583
// Unscoped recall runs from inside the active conversation, whose newest user
// message is commonly the question being recalled. Demote that one message,
// plus messages-search command/result pairs, instead of deleting tool results
// globally. Explicit conversation targets do not demote their newest user message.
if (!conversationId && options.currentConversationId) {
  const latestCurrentUser = records
    .filter((record) => record.message.conversation_id === options.currentConversationId &&
                        record.message.message_type === "user_message")
    .sort((a, b) => b.message.date.localeCompare(a.message.date))[0];
  if (latestCurrentUser) latestCurrentUser.isSearchEcho = true;
}
```

**当前对话里最新的那条用户消息，通常就是“正在被回忆的那个问题”本身。** 我们是先踩了这个坑、才读到这段代码的。

## 13.4 mini-letta 的实现

mini-letta 不做子 agent，直接给主 agent 一个 `recall_search` 工具（`src/tools/recall-tool.ts`）。检索本身（`src/recall/search.ts`）照搬了分词、`termFrequency`、BM25 和“检索调用/结果降权”。数据源是每个对话的 `messages.jsonl`——它从来不会被压缩改写，所以被移出上下文的消息都还在。

mock 模型新增一条规则：用户说“还记得 X 吗”，就调用 `recall_search({query: X})`，拿到结果后回答第一条命中。

### 踩坑记录 1：最佳答案是问题本身

第一次跑长对话测试，结尾的问答是：

```text
用户：还记得数据库端口吗？
  ⚙ recall_search({"query":"数据库端口"})
mini-letta：我在过去的对话里找到了：还记得数据库端口吗？
```

它找到了……问题本身。“还记得数据库端口吗？”是一条很短、而且包含查询词的消息，BM25 的长度归一化让它的分数最高。这正是 13.3 节那段注释描述的情况。我们照搬了“降权当前对话最新的用户消息”。

### 踩坑记录 2：降权降错了人

修完再跑，排名依旧：

```text
3.405 user "还记得数据库端口吗？"
2.999 user "我们的数据库端口是 5433，别用默认的 5432"
2.885 assistant "我在过去的对话里找到了：我们的数据库端口是 5433，别用默认的 5432"
```

问题没被降权。原因：在提问的这一回合里**发生了一次压缩**，压缩产生的摘要消息也是 user 角色，而且排在问题之后——于是“最新的用户消息”变成了摘要，被降权的是它。letta-code 没有这个问题，因为它的摘要被投影成独立的 `summary_message` 类型（`src/backend/local/local-message-projection.ts:196-206`），过滤条件 `message_type === "user_message"` 天然排除了它。

修复分两步：先把“最新用户消息”的判定改成“最新的、可检索的用户消息”；然后像 letta-code 一样给消息加上类型标记，不再靠嗅探内容：

```ts
// code/mini-letta @ v0.4  src/llm/types.ts
/** Harness-made messages: a compaction summary (letta's summary_message). */
kind?: "summary";

// src/recall/search.ts
function searchableText(message: Message): string | null {
  if (message.role === "user") {
    if (message.kind === "summary" || isReminderOnly(message.content)) return null;
    return stripReminders(message.content);
  }
  ...
}
...
const latestUser = conversationId === currentConversationId
  ? messages.filter((m) => m.role === "user" && searchableText(m) !== null).at(-1)?.id
  : undefined;
```

教训：**“同一个角色”不等于“同一种消息”**。harness 自己制造的消息（摘要、提醒）需要可识别的类型，否则每个下游功能都要重新发明一遍“这条是不是用户真说的”的判断。

### 回归测试

```ts
// test/v04-context.test.ts
// Regression: without demotion the question itself was the top hit.
expect(searchRecall({ home, agentId: agent.id, query: "数据库端口" })[0]?.text).toBe("还记得数据库端口吗？");
expect(
  searchRecall({ home, agentId: agent.id, query: "数据库端口", currentConversationId: "c1" })[0]?.text,
).toContain("5433");
```

第一条断言故意保留：不传 `currentConversationId` 时（比如从 CLI 直接搜），问题本身仍然排第一——这是合理的，CLI 用户没有“正在问的问题”。

## 13.5 运行与验证

```text
$ export MINI_LETTA_CONTEXT_WINDOW=1200
$ bun src/cli.ts chat -p "我们的数据库端口是 5433，别用默认的 5432" >/dev/null
$ （16 个无关话题，压缩 5 次）
$ bun src/cli.ts chat -p "还记得数据库端口吗？"

  ⚙ recall_search({"query":"数据库端口"})
  ✓ [2026-10-08T16:00:49.789Z · default · user] 我们的数据库端口是 5433，别用默认的 5432

  ⇣ compacted (context_pressure): 15 → 11 messages, ~474 → ~372 tokens
我在过去的对话里找到了：我们的数据库端口是 5433，别用默认的 5432
$ bun src/cli.ts search 数据库端口 | head -3
3.40	default	user	还记得数据库端口吗？
3.00	default	user	我们的数据库端口是 5433，别用默认的 5432
2.88	default	assistant	我在过去的对话里找到了：我们的数据库端口是 5433，别用默认的 5432
```

注意那一行 `compacted`：压缩恰好发生在工具结果之后、最终回答之前（同一回合的第 2 步）。这正是踩坑记录 2 的触发条件。

`tokenize` 的单元测试：

```ts
expect(tokenize("数据库端口是5433,用Postgres")).toEqual(["数据库端口是", "5433", "用", "postgres"]);
```

## 13.6 recall 与记忆的分工

recall 能找回一切，那还要记忆文件干什么？第 1 章的答案在这里有了具体的形状：

- recall 要求 agent **知道该去找**——“还记得 X 吗”这种明确的提问才会触发；
- “用户讨厌 npm”不会有人问，它必须常驻（core memory）；
- 第 15 章的反思子 agent 做的事，就是把 recall 里“值得常驻的东西”提炼进记忆文件。

## 13.7 练习

1. **巩固**：在两个对话里分别提到“部署脚本在 scripts/deploy.sh”，然后在第三个对话里检索“部署脚本”。结果来自哪个对话？分数为什么不同？
2. **扩展**：实现引号短语：`recall_search({query: '"5433" 端口'})` 要求结果必须包含 `5433`。参照 letta-code 的 `parseQuery`（`transcript-search.ts:277`）和 `matchesPhrase`（`:270`）。
3. **读源码**：letta-code 的 recall 是 `fork: true` 的子 agent。分叉意味着它继承了父对话的全部上下文——这对检索质量有什么好处？对成本呢？为什么 `memory` 子 agent 是 `fork: false`？（对照 `src/agent/subagents/builtin/memory.md`。）
