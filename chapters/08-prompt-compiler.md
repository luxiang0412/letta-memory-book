# 第 8 章 ★★ 系统提示编译器

> 本章目标：完整读懂 letta-code 把 MemFS 编译成系统提示的代码，写出一个和它**逐字节一致**的编译器，并学会用“差分测试”验证这一点。前置：第 5–7 章。对应代码：mini-letta `v0.3` `src/memory/compile.ts`。

## 8.1 编译器要回答的问题

给定一个记忆仓库的 HEAD，产出一段文本 `coreMemory`，替换系统提示里的 `{CORE_MEMORY}`。要决定的是：

1. **读哪些文件**——全部？只读 core？
2. **怎么渲染**——每个文件长什么样，顺序如何？
3. **按需记忆怎么露出**——让 agent 知道“有”，但不占地方；
4. **附带什么元信息**——agent id？时间？
5. **输出要稳定**——同样的 HEAD 必须产出同样的字节（第 9 章的缓存靠它）。

## 8.2 入口：`compileLocalSystemPrompt`

```ts
// src/backend/local/system-prompt-compilation.ts:432-461（节选）
export function compileLocalSystemPrompt(options: CompileLocalSystemPromptOptions): LocalCompiledSystemPrompt {
  const compiledAt = options.now ?? new Date();
  const memoryDir = options.memoryDir ?? getScopedMemoryFilesystemRoot(options.agent.id);
  const memfs = options.includeMemfs === false
    ? { content: "", format: undefined, revision: undefined }
    : renderMemfsProjection(memoryDir);
  const metadata = memfs.format === "memfs-v2"
    ? ""                                                   // v2：不加 memory_metadata
    : compileMemoryMetadata({ agentId: options.agent.id, conversationId: options.conversationId,
                              compiledAt, previousMessageCount: options.previousMessageCount ?? 0 });
  const coreMemory = [memfs.content, metadata].filter((part) => part.trim().length > 0).join("\n\n");
  return {
    content: injectCoreMemory(options.agent.system, coreMemory),
    coreMemory,
    compiledAt: compiledAt.toISOString(),
    rawSystemHash: hashRawSystemPrompt(options.agent.system),
    memfsRevision: memfs.revision,
  };
}
```

返回值里除了最终的 `content`，还有三样“指纹”：`coreMemory`（单独的记忆部分，第 9 章的 `<memory_update>` 要用）、`rawSystemHash`（原始系统提示的 sha256）、`memfsRevision`（HEAD）。

**v2 不加 `<memory_metadata>`。** v1 时代的元信息里有对话 id、编译时间和消息数。v2 去掉了它们——代码没有写理由，我们的推测是：这些字段让每个对话、每次编译的系统提示都不一样，而去掉之后，**同一个 HEAD 在所有对话里编译出完全相同的字节**，更利于提示缓存，也让“编译结果只取决于记忆”这件事成立。（mini-letta v0.3 跟随了这个选择；agent id、记忆目录这类信息改由对话开头的一条 agent-info 提醒提供，第 9 章。）

## 8.3 读哪些文件：只读需要的

```ts
// src/backend/local/system-prompt-compilation.ts:91-119（节选）
paths = gitOutput(memoryDir, ["ls-tree", "-r", "--name-only", "HEAD"])
  .split("\n").map((path) => normalizePath(path.trim()))
  .filter((path) => path.length > 0 && path.endsWith(".md"));
const format: LocalMemoryFormat = paths.includes("MEMORY.md") ? "memfs-v2" : "memfs-v1";
const allPaths = new Set(paths);
for (const relativePath of paths) {
  const shouldRead =
    format === "memfs-v1" ||
    isCoreMemoryPath(relativePath, format) ||
    (/^[^/]+\/MEMORY\.md$/.test(relativePath) && isProjectedMemoryPath(relativePath, allPaths, format));
  if (!shouldRead) {
    files.push({ relativePath, label: labelFromPath(relativePath), value: "", description: "" });
    continue;                                  // 只登记路径，不读内容
  }
  const raw = gitOutput(memoryDir, ["show", `HEAD:${relativePath}`]);
  ...
}
```

两点：

- **格式由 HEAD 决定**：`paths.includes("MEMORY.md")`，看的是已提交的树（而 `detectMemoryFormat` 看的是工作区）。编译器从头到尾不碰工作区。
- **只读需要渲染的文件**：v2 只对根目录的 core 文件和**第一层**子目录的 `MEMORY.md` 调用 `git show`。其余文件只登记路径。一个有几百个按需文件的仓库，编译成本只和 core 文件的数量有关。

读出的内容经 `parseFrontmatter()`（`src/utils/frontmatter.ts:73`）拆成 frontmatter 和正文；它会去掉 BOM、把 CRLF 归一化为 LF、并 `trim()` 正文——记住这一点，8.6 节它会出场。最后按 label 排序（`:139`，`files.sort((a, b) => a.label.localeCompare(b.label))`），保证输出稳定。

## 8.4 怎么渲染：`renderRootMemoryProjection`

```ts
// src/backend/local/system-prompt-compilation.ts:154-198（节选）
for (const file of rootFiles) {                       // 根目录 core 文件，除 MEMORY.md，按 label 排序
  const lines = [`<${file.label}>`];
  const description = file.description.trim();
  if (description) lines.push(`<description>${description}</description>`);
  const value = file.value.trimEnd();
  if (value) lines.push(value);
  lines.push(`</${file.label}>`);
  blocks.push(lines.join("\n"));
}
if (rootIndex) {                                       // 根 MEMORY.md
  const lines = ["<memory>"];
  const value = rootIndex.value.trimEnd();
  if (value) lines.push(value);
  if (childIndexes.length > 0) lines.push("<deferred-memory>");
  for (const file of childIndexes) {
    const directory = file.relativePath.slice(0, -"/MEMORY.md".length);
    const escaped = escapeXmlAttribute(directory);
    lines.push(`<directory path="${escaped}/" index="${escaped}/MEMORY.md" />`);
  }
  if (childIndexes.length > 0) lines.push("</deferred-memory>");
  lines.push("</memory>");
  blocks.push(lines.join("\n"));
}
return blocks.join("\n\n");
```

渲染规则：

| 来源 | 输出 |
|---|---|
| 根目录 `foo.md`（frontmatter 的 `description` + 正文） | `<foo>` `<description>…</description>` 正文 `</foo>` |
| 根目录 `MEMORY.md` | `<memory>` 正文 … `</memory>` |
| 第一层子目录索引 `projects/MEMORY.md` | 在 `<memory>` 里一行 `<directory path="projects/" index="projects/MEMORY.md" />` |
| 其余按需文件、技能 | 不出现 |

几个设计细节：

- **子目录只给路径，不给内容**——连子目录 `MEMORY.md` 的正文都不放。agent 想知道里面有什么，要自己读。
- **目录名做了 XML 属性转义**（`escapeXmlAttribute`），因为它来自 agent 可控的路径。
- **标签名就是文件名**：`human.md` → `<human>`。这是从“记忆块”时代继承来的形状：模型早已习惯 `<persona>`、`<human>`。
- **注入点**：`injectCoreMemory()`（`:380`）——没有 `{CORE_MEMORY}` 就追加到末尾。

v1 的渲染（`renderMemfsProjection` 的另一半，`:305` 起）复杂得多：`persona` 被单独放进 `<self>`，`system/` 下的文件渲染成带 `<projection>` 路径的嵌套树，其余文件以一棵 `<external_projection>` 目录树列出。v2 把这些都简化成了“根文件 + 索引”。

## 8.5 自己实现

mini-letta v0.3 的编译器：

```ts
// code/mini-letta @ v0.3  src/memory/compile.ts（节选）
const CHILD_INDEX = /^[^/]+\/MEMORY\.md$/;

export function readCommittedMemory(memoryDir: string) {
  const revision = headRevision(memoryDir);
  if (!revision) return { files: [] };
  const paths = git(memoryDir, ["ls-tree", "-r", "--name-only", "HEAD"]).stdout.split("\n")
    .filter((path) => path.endsWith(".md"));
  const allPaths = new Set(paths);
  const files = paths.map((relativePath) => {
    const needsBody = isCoreMemoryPath(relativePath) ||
      (CHILD_INDEX.test(relativePath) && isProjectedMemoryPath(relativePath, allPaths));
    const raw = needsBody ? git(memoryDir, ["show", `HEAD:${relativePath}`]).stdout : "";
    const { frontmatter, body } = parseFrontmatter(raw);
    return { relativePath, label: labelFromPath(relativePath), description: frontmatter.description ?? "", body };
  });
  files.sort((a, b) => a.label.localeCompare(b.label));
  return { files, revision };
}
```

`renderCoreMemory()` 与 letta-code 的 `renderRootMemoryProjection()` 规则相同（mini 省略了 XML 转义——练习 2）。`compileSystemPrompt()` 返回同样的四个字段：`content`、`coreMemory`、`compiledAt`、`rawSystemHash`、`memfsRevision`。

单元测试锁定了输出格式：

```ts
// test/v03-compile.test.ts
expect(out).toBe([
  "<human>", "<description>The user</description>", "- likes pnpm", "</human>", "",
  "<memory>", "# Memory", "- [projects](projects/MEMORY.md)",
  "<deferred-memory>", '<directory path="projects/" index="projects/MEMORY.md" />', "</deferred-memory>",
  "</memory>",
].join("\n"));
```

## 8.6 差分测试：和 letta-code 的编译器对拍

单元测试只能证明 mini-letta 符合**我们以为的**规则。要证明它符合 letta-code 的**实际**行为，最直接的办法是对拍：在同一个记忆仓库上分别运行两个编译器，比较输出。

我们用 Lab 6 的演示脚本生成了一个有三个根文件、一个带索引的子目录和一个技能的仓库，然后在 letta-code `70ead335` 的本地克隆里运行：

```ts
// 一次性脚本（在 letta-code 克隆里运行）
import { compileLocalSystemPrompt } from "@/backend/local/system-prompt-compilation";
const out = compileLocalSystemPrompt({
  agent: { id: "agent-demo", system: "SYSTEM {CORE_MEMORY}" } as never,
  conversationId: "c", memoryDir: MEM, includeMemfs: true,
});
process.stdout.write(out.coreMemory);
```

mini-letta 这边用 `compileSystemPrompt()` 做同样的事。第一次 `diff` 的结果：

```text
2a3
>
```

只差一行：mini-letta 在 `<human>` 的描述之后多了一个空行。原因是 `human.md` 初始正文为空，后来追加的行前面留着一个换行；letta-code 的 `parseFrontmatter()` 会 `trim()` 正文（`src/utils/frontmatter.ts:163` 的 `body: body.trim()`），还会去 BOM、归一化 CRLF（`:81-84`），而 mini-letta 的版本没有。修好之后：

```text
$ diff letta-compiled.txt mini-compiled.txt && echo IDENTICAL
IDENTICAL
```

两边逐字节一致的输出（599 字节）：

```text
<human>
<description>What I know about the user.</description>
- 我叫小陆，主要写 TypeScript
- 我更喜欢用 tabs 缩进
</human>

<persona>
<description>Who I am and how I behave.</description>
I am mini-letta, a helpful assistant that remembers.
- 回答末尾总是加上 🦉
</persona>

<memory>
# Memory

- [persona](persona.md) — Who I am and how I behave.
- [human](human.md) — What I know about the user.
- [projects](projects/MEMORY.md) — project notes, read on demand
<deferred-memory>
<directory path="projects/" index="projects/MEMORY.md" />
</deferred-memory>
</memory>
```

`projects/mini-letta.md` 的内容和 `skills/release-notes/SKILL.md` 都没有出现——这正是渐进式披露。修复连同一个回归测试（`parseFrontmatter matches letta-code: BOM, CRLF, trimmed body`）提交在 mini-letta 的 `v1.0` 上。

> 对拍是“照着一个大系统重写一个小系统”时最有效的验证手段。它找到的往往不是逻辑错误，而是这种你根本想不到要测的细节——一个 `trim()`。

## 8.7 设计取舍

| 选择 | 好处 | 代价 |
|---|---|---|
| 只读 HEAD | 半成品不泄漏；版本号明确 | 每次编译都要 `git` 子进程（letta-code 用 `execFileSync`，同步） |
| 只读 core 与第一层索引 | 编译成本与按需记忆数量无关 | 更深的目录要靠索引里的链接被发现 |
| 标签名 = 文件名 | 延续 block 时代的提示形状 | 文件名必须是合法的 XML 标签名（`my notes.md` 会怎样？练习 3） |
| v2 去掉元信息 | 输出只取决于 HEAD，跨对话稳定 | agent id 等信息要另找渠道（agent-info 提醒） |

## 8.8 练习

1. **巩固**：在 mini-letta 里新建 `projects/MEMORY.md` 和 `projects/a.md` 并提交，用 `bun src/cli.ts prompt --fresh` 看输出；再建 `projects/sub/MEMORY.md`，它会出现在 `<deferred-memory>` 里吗？
2. **扩展**：给 `renderCoreMemory` 加上目录名的 XML 属性转义，并写一个包含 `"` 和 `<` 的目录名测试。
3. **读源码**：如果一个根文件叫 `my notes.md`，letta-code 渲染出的标签是 `<my notes>`——这不是合法的 XML。hook 会拦住这种文件名吗？（看 `validateMemoryFileFrontmatter` 和 `validateMemoryTreeConstraints`。）这算不算问题？模型真的需要合法的 XML 吗？
