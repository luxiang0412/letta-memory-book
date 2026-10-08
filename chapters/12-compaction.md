# 第 12 章 压缩：滑动窗口、摘要与上下文 id 列表

> 本章目标：读懂 letta-code 的本地压缩——在哪里切、怎么写摘要、摘要以什么形式放回上下文、压缩后系统提示为什么要重编译——并实现一个行为一致的版本。前置：第 11 章。对应代码：mini-letta `v0.4` `src/context/{compaction,compact-conversation}.ts`、`src/store/conversation-store.ts`。

## 12.1 压缩不是删除

letta-code 的系统提示对 agent 是这样描述压缩的（`letta_no_memfs.md:27`）：“Older messages get summarized through compaction — compaction is summarization, not loss. The originals remain searchable via recall, but your memory is the ground truth for what mattered.”

三层意思：

1. 压缩把**一段旧消息**换成**一条摘要**，只改变“上下文窗口里有什么”；
2. 原始消息还在 recall 里（第 13 章）；
3. 真正重要的东西应该早已写进记忆文件——摘要是会丢细节的。

所以存储上要区分两件事：**全部消息**（只追加）和**当前在上下文里的消息**（一个 id 列表）。letta-code 的对话对象上有 `in_context_message_ids`；压缩时把它改成 `[摘要, ...保留的消息]`（`src/backend/local/local-store.ts:1201`）。

## 12.2 两种模式

```ts
// src/backend/local/compaction.ts:43-46
export const LOCAL_DEFAULT_COMPACTION_MODE = "sliding_window";
export const LOCAL_DEFAULT_SLIDING_WINDOW_PERCENTAGE = 0.3;
export type LocalCompactionMode = "all" | "sliding_window";
```

- **sliding_window**（默认）：摘要掉最前面的一部分，保留最近的消息原文；
- **all**：全部摘要，只保留一个还没得到结果的工具调用（如果有）。

编排在 `compactLocalConversationInner()`（`src/backend/local/local-backend.ts:727`）：先试滑动窗口；规划失败、或者压完还是超过窗口，就退回 `all`；**两条路的最后都完整重编译系统提示**（`:760`、`:784`）。

## 12.3 在哪里切：`planLocalSlidingWindowCompaction`

```ts
// src/backend/local/compaction.ts:584-650（节选）
const maximumCutoffIndex = lastMessage && hasPendingLocalToolCall(lastMessage)
  ? messages.length - 2 : messages.length - 1;
const goalTokens = (1 - percentage) * options.contextWindow;     // 保留部分要小于窗口的 70%
let approxTokenCount = options.contextWindow ?? Number.POSITIVE_INFINITY;
let cutoffIndex: number | undefined;
let evictionPercentage = percentage;
while ((goalTokens === undefined ? cutoffIndex === undefined : approxTokenCount >= goalTokens)
       && evictionPercentage < 1.0) {
  evictionPercentage += 0.1;                                      // 第一次就是 0.4
  const messageCutoffIndex = Math.min(Math.round(evictionPercentage * messages.length), messages.length - 1);
  cutoffIndex = [...Array(messageCutoffIndex + 1).keys()].reverse()
    .find((index) => isValidSlidingWindowCutoff(messages, index, maximumCutoffIndex));
  if (cutoffIndex === undefined) continue;
  approxTokenCount = estimateLocalMessageTokens(messages.slice(cutoffIndex));
}
```

规则：

1. **只在 assistant 消息前面切**（`isValidSlidingWindowCutoff`：`role === "assistant"`、不是第一条、在最大切点之前）。工具结果总是紧跟在发出调用的 assistant 消息之后，所以“在 assistant 前切”保证了**工具调用和它的结果不会被拆开**——拆开的话，很多 API 会直接拒绝请求。
2. **最后一条是未完成的工具调用时，留它和它前面一条**（`maximumCutoffIndex`）。
3. **淘汰比例从 30% 起步，每次加 10%**——注意加法在计算之前，所以第一次尝试就是 40%。直到保留部分的估算小于窗口的 70%。
4. 找不到切点，或者比例加到了 100%，抛 `LocalSlidingWindowCompactionPlanningError`，上层退回 `all`。

一个浮点数细节：从 0.3 开始**连加** 7 次 0.1，得到的是 `0.9999999999999999`（而 `0.3 + 0.1 * 7` 恰好是 `1.0`——这正是逐次累加误差），小于 1。所以如果到这一步保留部分还没达标，循环会再跑一轮，把比例加到 `1.0999…`、算出一个切点，然后退出——而退出后的检查 `evictionPercentage >= 1.0` 会让这最后一轮的结果作废，转去 `all` 模式。mini-letta 原样保留了这个行为。

## 12.4 怎么写摘要

两份提示词：`LOCAL_ALL_COMPACTION_PROMPT`（`:61`）和 `LOCAL_SLIDING_WINDOW_COMPACTION_PROMPT`（`:85`）。滑动窗口版的要点：

- 这些消息正从上下文**开头**被移走，摘要要放在剩余消息**之前**，为它们提供背景；
- 分节：高层目标、发生了什么、重要细节（**标识符原样保留**：文件路径、URL、PR 号、工单号）、错误与修复、**查找线索**（放不下的细节，记下以后能在历史里搜到它的关键词）；
- 如果被移走的部分里本身就有旧摘要，要把它提炼进来；
- 不超过 300 词（`SLIDING_WORD_LIMIT`，`:23`）。

“查找线索”这一节把压缩和 recall 连了起来：摘要不必记住一切，但要记住**怎么找回**。

转写给摘要模型的对话记录，工具结果截断到 2 000 字符（`LOCAL_SUMMARY_TOOL_RETURN_TRUNCATION_CHARS`，`:25`）；如果记录本身太大、摘要请求也溢出，就按 `TRANSCRIPT_FALLBACK_MAX_CHAR_STEPS`（`:31`，从 120 000 一路降到 2 000 字符）逐级缩短重试。摘要返回后还有一道硬截断：超过 `clip_chars`（默认 50 000 字符）就截断并加上 `... [summary truncated to fit]`（`:544`）。

## 12.5 摘要以什么形式回到上下文

```ts
// src/backend/local/compaction.ts:682-707（节选）
message = `Note: ${numEvicted} messages from the beginning of the conversation have been hidden from view due to memory constraints.\nThe following is a summary of the previous messages:\n ${summary}`;
return JSON.stringify({ type: "system_alert", message, time: new Date().toISOString(),
                        ...(stats ? { compaction_stats: stats } : {}) });
```

它被存成一条 **user 角色**的消息，内容是这段 JSON；`metadata.compaction` 里另存一份摘要和统计（`local-store.ts:1157` 起的 `compactConversationAll()`）。对外投影成消息列表时，它不是普通的 user 消息，而是一个单独的 `summary_message` 类型（`src/backend/local/local-message-projection.ts:196`）——第 13 章会看到这个区分有多重要。

## 12.6 压缩之后：重编译系统提示

第 9 章说过，对话中途的记忆变化不会改系统提示（保缓存）。压缩是个例外：上下文已经被重写，缓存反正要失效，于是**顺便**把系统提示完整重编译一次，把这段时间积累的记忆变化折叠进去。从提示缓存的角度看，这是“免费”的。

mini-letta 也这样做：`compactConversation()` 最后调用 `invalidateSystemPrompt(store)`。更妙的是，mini-letta 持久化的 `<memory_update>` 提醒恰好也在被摘要的旧消息里——压缩之后，它们连同旧消息一起消失，而新系统提示已经包含了最新记忆。两个机制自然地咬合在一起。

## 12.7 mini-letta 的实现

**上下文 id 列表**（`src/store/conversation-store.ts`）：

```ts
append(...messages: Message[]): void {
  // ...追加到 messages.jsonl...
  const context = this.readJson<{ inContextIds: string[] }>(CONTEXT);
  if (context) {
    this.writeJson(CONTEXT, { inContextIds: [...context.inContextIds, ...messages.map((m) => m.id)] });
  }
}

/** Messages currently in the context window, in order. */
inContext(): Message[] {
  const all = this.all();
  const context = this.readJson<{ inContextIds: string[] }>(CONTEXT);
  if (!context) return all;                      // 从未压缩过：全部都在上下文里
  const byId = new Map(all.map((m) => [m.id, m]));
  return context.inContextIds.flatMap((id) => byId.get(id) ?? []);
}
```

**规划**（`src/context/compaction.ts` 的 `planSlidingWindow`、`planAll`）是 letta-code 那两个函数的直译。

**编排**：

```ts
// code/mini-letta @ v0.4  src/context/compact-conversation.ts（节选）
export async function compactConversation(input: { store; provider; trigger }): Promise<CompactionStats> {
  const messages = store.inContext();
  const window = provider.contextWindow;
  let plan: CompactionPlan;
  try {
    plan = planSlidingWindow(messages, { contextWindow: window });
    if (estimateMessagesTokens(plan.messagesToKeep) >= window) plan = planAll(messages);
  } catch (error) {
    if (!(error instanceof CompactionPlanningError)) throw error;
    plan = planAll(messages);
  }
  const summary = await summarize(provider, plan.messagesToSummarize);
  const summaryMessage = makeMessage("user", packageSummary(summary, stats), { kind: "summary" });
  store.append(summaryMessage);
  store.setContext([summaryMessage.id, ...plan.messagesToKeep.map((m) => m.id)]);
  invalidateSystemPrompt(store);                                   // 压缩后完整重编译
  store.writeJson(COMPACTION_EVENT, { pending: true, at: new Date().toISOString(), stats });  // 第 14 章用
  return stats;
}
```

`kind: "summary"` 是后来加的（第 13 章的踩坑记录）。

**mock 摘要器**故意很“笨”：只保留每条用户消息的前 12 个字符。这样被压缩掉的细节就真的不在摘要里了，能逼出第 13 章的 recall。

## 12.8 运行与验证

```ts
// test/v04-context.test.ts
const messages = conversation(10);   // 20 条消息，每条 27 token
const roomy = planSlidingWindow(messages, { contextWindow: 1_000 });
expect(roomy.messagesToKeep[0]?.role).toBe("assistant");
// First attempt evicts 40%: round(0.4 * 20) = 8 → index 7 is the nearest assistant.
expect(roomy.messagesToSummarize.length).toBe(7);
// A tighter window keeps growing the cut (50%, 60%) until the tail fits 70%.
const tight = planSlidingWindow(messages, { contextWindow: 400 });
expect(tight.messagesToSummarize.length).toBe(11);
```

（这个测试我们第一次写错了：用 400 的窗口却期望切在 7——忘了 40% 不够时会继续加到 50%、60%。测试失败告诉我们的是“我对算法的理解错了”，而不是代码错了。）

CLI 演示（窗口 1 200）：

```text
$ export MINI_LETTA_HOME=$(mktemp -d) MINI_LETTA_CONTEXT_WINDOW=1200
$ bun src/cli.ts chat -p "我们的数据库端口是 5433，别用默认的 5432" >/dev/null
$ for i in $(seq 0 15); do bun src/cli.ts chat -p "第 $i 个无关话题：..." | grep compacted; done
  ⇣ compacted (context_pressure): 17 → 11 messages, ~462 → ~365 tokens
  ⇣ compacted (context_pressure): 15 → 11 messages, ~467 → ~363 tokens
  ⇣ compacted (context_pressure): 15 → 11 messages, ~465 → ~363 tokens
  ⇣ compacted (context_pressure): 15 → 11 messages, ~465 → ~363 tokens
  ⇣ compacted (context_pressure): 15 → 11 messages, ~465 → ~363 tokens
```

### 观察：小窗口里的锯齿

压缩大约每两个回合发生一次，每次都是 15 → 11 条。原因是规划器的目标“保留部分 < 窗口的 70%”只算**消息**，没算 524 token 的地板（系统提示 + 工具）。在 1 200 的窗口里：保留 ~363 + 地板 524 + 新回合 ~50 ≈ 940，离阈值 960 只差一点，下两个回合就又超了。letta-code 的口径相同，但在 200k 的窗口里地板只占百分之几，问题几乎不可见。小窗口本地模型的用户会更容易遇到这种“频繁压缩”——练习 2。

### 踩坑记录：真模型写的摘要不听话

用 `qwen2.5:3b` 做摘要器（`MINI_LETTA_PROVIDER=openai bun src/cli.ts compact`）：

```text
{"trigger":"manual","messagesBefore":12,"messagesAfter":8,"tokensBefore":382,"tokensAfter":370}
Note: 5 messages from the beginning of the conversation have been hidden from view due to memory constraints.
The following is a summary of the previous messages:
 根据提供的信息，用户似乎在讨论天气情况，但对话中包含了大量重复的“今天天气不错”这一话题。……
 隐藏的对话内容包括用户提到的“今”和“今”两个话题，……
 隐藏这些内容的原因是，它们与用户的主要讨论目标（了解天气情况）不相关。……
```

382 → 370：几乎没省。“不超过 300 词”被无视，摘要里还编造了“隐藏是因为不相关”这种解释，并把前一次 mock 摘要的残片（“今；今”）当成了内容。我们照着 letta-code 的 `clip_chars` 加了一道硬截断——但 50 000 字符对 1 200 token 的窗口毫无意义，所以按窗口缩放：最多窗口的 10%：

```ts
// code/mini-letta @ v0.4  src/context/compaction.ts
export function clipSummary(summary: string, contextWindow: number): string {
  const clipChars = Math.max(200, Math.floor(contextWindow * 4 * 0.1));
  return summary.length > clipChars ? `${summary.slice(0, clipChars)}${SUMMARY_TRUNCATION_SUFFIX}` : summary;
}
```

再跑一次：`{"messagesBefore":8,"messagesAfter":6,"tokensBefore":370,"tokensAfter":337}`。

教训：**摘要的长度不能交给模型自觉**；任何“请控制在 N 字以内”的指令都需要一个代码层的上限。

## 12.9 练习

1. **巩固**：手动执行 `bun src/cli.ts compact`，然后对比 `messages.jsonl` 和 `context.json`：哪些 id 不见了？摘要消息的 `kind` 是什么？
2. **扩展**：让规划器把地板也算进去：目标改为 `messages + floor < (1 - percentage) × window`。用 1 200 窗口重跑 17 回合，压缩次数和每次保留的消息数怎么变？
3. **读源码**：`planLocalAllCompaction()`（`src/backend/local/compaction.ts:652`）在最后一条是未完成工具调用时只保留那一条。为什么 `all` 模式下保留它就够了，而不需要保留它前面的消息？
