# 第 11 章 上下文预算：估算、阈值与“地板”

> 本章目标：知道 harness 怎么估算一次请求有多大、什么时候必须压缩、以及为什么要在请求**之前**就压缩而不是等服务商报错。前置：第 8–9 章。对应代码：mini-letta `v0.4` `src/context/tokens.ts`、`src/context/compaction.ts`。

## 11.1 一次请求由什么组成

```text
请求 = 系统提示（含 core memory） + 工具定义 + 上下文里的消息 + 模型要生成的输出
```

前两项是**地板**：每一次请求都要付，和对话长短无关。第三项随对话增长。第四项是给模型“写回答”留的空间。上下文窗口必须同时装下这四样。

mini-letta 的一个真实测量（v0.4，默认系统提示 + 5 个工具，`chars/4` 估算）：

```text
system 221   tools 303   total 524        ← 一条消息都还没有
一条“第 N 个无关话题：今天天气不错。×12”消息 ≈ 24 tokens
```

**工具定义比系统提示还大。**在真实的 coding agent 里，几十个工具的 JSON Schema 轻松上万 token。letta-code 的系统提示在讲 mods 时也提醒过 agent：“each active schema consumes context”（`letta_root_memfs.md:185`）。

## 11.2 估算：先粗后精

没有 tokenizer 也能估：letta-code 的本地后端用和我们一样的 4 字符 ≈ 1 token：

```ts
// src/backend/local/local-context-estimate.ts:79-93（节选）
export function estimateLocalMessageTokens(message: LocalMessage): number {
  let chars = 0;
  if (message.role === "user") {
    if (typeof message.content === "string") {
      chars = message.content.length;
    } else {
      for (const block of message.content) {
        if (block.type === "text") chars += textLength(block.text);
        else if (block.type === "image") chars += IMAGE_TOKEN_ESTIMATE * 4;   // 图片按 1200 token 计
      }
    }
    return Math.ceil(chars / 4);
  }
  ...
}
```

但估算只是兜底。一旦有了服务商返回的 **usage**，就以它为准：`estimateLocalContextTokens()`（`:164`）找到最近一条带 usage 的 assistant 消息，用它报告的 token 数（`input + output + cacheRead + cacheWrite`，`contextTokensFromLocalUsage()`，`:40`），再加上它**之后**新增消息的估算值。

两个细节：

- **缓存的 token 也算**。Anthropic 的 `input_tokens` 不含缓存命中的部分，真正的上下文大小是 `input + cache_creation + cache_read`——letta-code 的 CLAUDE.md 专门警告过：“Getting this wrong breaks summarizer triggering.”
- **压缩边界之前的 usage 作废**。压缩后，旧的 usage 描述的是压缩前的上下文，不能再用（`latestCompactionBoundaryTimestamp()`，`:124`，按时间戳判断，注释解释了为什么不能按数组顺序）。

mini-letta 只实现了估算部分（`src/context/tokens.ts`）：它的 provider 接口不返回 usage。

## 11.3 阈值：为什么是 16384

```ts
// src/backend/dev/provider-turn-executor.ts:34-35, 241-259
const LOCAL_CONTEXT_COMPACTION_RESERVE_TOKENS = 16_384;
const LOCAL_SMALL_CONTEXT_COMPACTION_RESERVE_RATIO = 0.2;

export function contextCompactionThreshold(contextWindow: number | undefined): number | undefined {
  if (typeof contextWindow !== "number" || !Number.isFinite(contextWindow) || contextWindow <= 0) {
    return undefined;
  }
  const reserveTokens = Math.min(
    LOCAL_CONTEXT_COMPACTION_RESERVE_TOKENS,
    Math.max(1, Math.floor(contextWindow * LOCAL_SMALL_CONTEXT_COMPACTION_RESERVE_RATIO)),
  );
  return Math.max(0, contextWindow - reserveTokens);
}
```

预留 16 384 token 给输出，小窗口则最多预留 20%。几个窗口下的阈值（mini-letta 的测试里逐一断言过）：

| 窗口 | 预留 | 超过多少就压缩 |
|---|---|---|
| 200 000 | 16 384 | 183 616 |
| 32 000 | 6 400 | 25 600 |
| 2 000 | 400 | 1 600 |

这段代码上面有一大段注释（`:225-240`），解释了**为什么必须在请求之前压缩**。大意是：pi-ai 为了让一个超大的请求“合法”，会把输出额度压到 `contextWindow - 估算上下文 - 4096`，最低 1 个 token。于是一个快满的请求**不会报上下文溢出的错**，而是生成到一半以 `length` 停止——“我们的重试路径根本抓不到”。所以必须由 harness 在发请求之前判断：快满了，先压缩。注释还附上了 pi 编码 agent 里同样数值的出处链接（固定到某个 commit），这是在照搬一个已经被验证过的策略。

判断发生在 provider 适配层的 preflight（`src/backend/dev/pi-stream-adapter.ts:562`），压缩回调最终落到 `LocalBackend.compactForContextPressure()`（`src/backend/local/local-backend.ts:551`）。拿到响应之后、usage 已知时还会再判断一次（`pi-stream-adapter.ts:767`）。

## 11.4 地板太高怎么办

如果光系统提示 + 工具就超过了窗口，压缩消息也没用。letta-code 在发请求前检查这个“地板”（`estimateProviderPromptFloorTokens()`，`provider-turn-executor.ts:215`），超过就直接报错并给出建议（`assertPromptFloorFitsContextWindow()`，`pi-stream-adapter.ts:361`）——对 Ollama，它会建议 `OLLAMA_CONTEXT_LENGTH=<下一个 2 的幂> ollama serve`。

这对用本地小模型的人很实用：Ollama 默认的上下文窗口很小，letta-code 的系统提示加工具定义很容易就超过它。

## 11.5 mini-letta 的实现

```ts
// code/mini-letta @ v0.4  src/context/compaction.ts（节选）
export const COMPACTION_RESERVE_TOKENS = 16_384;
export const SMALL_CONTEXT_RESERVE_RATIO = 0.2;

export function compactionThreshold(contextWindow: number): number {
  const reserve = Math.min(COMPACTION_RESERVE_TOKENS,
    Math.max(1, Math.floor(contextWindow * SMALL_CONTEXT_RESERVE_RATIO)));
  return Math.max(0, contextWindow - reserve);
}

export function shouldCompact(contextTokens: number, contextWindow: number): boolean {
  return contextTokens > compactionThreshold(contextWindow);
}
```

循环里，每一步在调用模型之前：

```ts
// code/mini-letta @ v0.4  src/agent/loop.ts（节选）
let request = prepare();                     // 系统提示 + 在上下文中的消息 + 工具
// Compact BEFORE the request when usage nears the window (not only after an overflow).
if (shouldCompact(estimateRequestTokens(request), provider.contextWindow)) {
  await compact("context_pressure");
  request = prepare();
}
try {
  response = await provider.complete(request, ...);
} catch (error) {
  if (!(error instanceof ContextOverflowError)) throw error;
  await compact("context_overflow");         // 兜底：估算失准时，服务商报错后再压缩一次
  request = prepare();
  response = await provider.complete(request, ...);
}
```

为了让溢出路径也能被测到，mock 模型像真实服务商一样**拒绝**超过窗口的请求（抛 `ContextOverflowError`）。OpenAI 兼容客户端则把 HTTP 错误里带 “context / too long / maximum…tokens” 的情况映射成同一个错误类型。

## 11.6 运行与验证

```ts
// test/v04-context.test.ts
expect(compactionThreshold(200_000)).toBe(183_616);
expect(compactionThreshold(32_000)).toBe(25_600);
expect(compactionThreshold(2_000)).toBe(1_600);
```

用一个 1 200 token 的窗口（阈值 960）跑 17 个回合，压缩全部由 `context_pressure` 触发，一次溢出都没有发生：

```text
compactions: {"trigger":"context_pressure","messagesBefore":17,"messagesAfter":11,"tokensBefore":461,"tokensAfter":365}
{"trigger":"context_pressure","messagesBefore":15,"messagesAfter":11,"tokensBefore":467,"tokensAfter":363}
{"trigger":"context_pressure","messagesBefore":15,"messagesAfter":11,"tokensBefore":465,"tokensAfter":363}
...（共 5 次）
```

注意这些 `tokensBefore/After` 只统计**消息**，不含 524 token 的地板。第 12 章会看到，这个“只算消息”的口径在小窗口里会造成压缩的锯齿。

## 11.7 练习

1. **巩固**：计算窗口为 8 192、128 000、1 000 000 时的阈值，写进测试。
2. **扩展**：给 `LLMProvider.complete()` 的返回值加上 `usage`（OpenAI 兼容接口的 `usage.prompt_tokens`），并实现“usage 优先、估算兜底”的 `estimateContextTokens()`。压缩之后要怎样让旧的 usage 失效？
3. **读源码**：读 `src/backend/dev/provider-turn-executor.ts:225-240` 的注释和它引用的两个 pi 源码链接。为什么注释特意说“an intentionally small `max_tokens` value remains a normal provider length stop”？如果阈值按 `max_tokens` 而不是固定预留来算，会出什么问题？
