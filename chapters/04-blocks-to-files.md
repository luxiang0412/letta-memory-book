# 第 4 章 从 memory block 到 memory file

> 本章目标：理解 letta-code 为什么把“记忆块”变成了“记忆文件”，以及一个块是怎样被翻译成一个带 frontmatter 的 Markdown 文件的。前置：第 1–3 章。对应代码：mini-letta `v0.2` `src/memory/memfs.ts`。

## 4.1 记忆块：MemGPT 的原始形态

在 MemGPT/Letta 服务器里，core memory 由若干**块（block）**组成，每个块有：

| 字段 | 含义 |
|---|---|
| `label` | 名字，渲染时就是 XML 标签名，如 `<persona>` |
| `value` | 正文 |
| `description` | 给模型看的“这个块是干什么的” |
| `limit` | 字符上限 |
| `read_only` | agent 不可改（由别的工具管理） |

letta-code 里还能看到它们的痕迹。新 agent 默认的两个块来自 `.mdx` 文件：

```ts
// src/agent/memory.ts:16
export const MEMORY_BLOCK_LABELS = ["persona", "human"] as const;
```

```markdown
<!-- src/agent/prompts/persona.mdx -->
---
label: persona
description: Who I am, what I value, and how I approach working with people. This evolves as I learn and grow.
---

I'm a coding assistant, ready to be shaped by how we work together.
```

`.mdx` 用 `parseMdxFrontmatter()`（`src/agent/memory.ts:26`）解析成 `{label, value, description}`。只读块的名单在 `src/agent/memory-constants.ts:1`：只有一个 `memory_filesystem`——那是 harness 生成的“记忆文件树视图”，agent 当然不该手改。

块的问题在于：**它是数据库里的一个字符串字段。** agent 只能通过专门的工具（`core_memory_append`、`core_memory_replace`……）去改它；人想看历史、想 diff、想批量整理，都要专门做 UI。

## 4.2 关键一步：块就是文件

MemFS 的想法很直接：既然 agent 已经非常擅长用 shell 和编辑器改文件，那就**把每个块变成一个文件**，把整组块变成一个 git 仓库：

| 块的概念 | 文件的对应物 |
|---|---|
| `label` | 文件路径（去掉 `.md`） |
| `value` | 文件正文 |
| `description` | frontmatter 里的 `description` |
| 渲染进系统提示的顺序 | 按路径排序 |
| `limit` | `.memfs.config.json` 的字符预算（第 7 章） |
| `read_only` | v1：frontmatter 受保护字段；v2：`readOnlyFiles` glob（第 7 章） |
| 修改历史 | `git log` |
| 修改工具 | 任何能改文件的工具 + `git commit` |

收益是巨大的：grep、diff、blame、revert、分支、远端同步、人类用 VS Code 打开就能编辑……全都免费得到。代价是：**文件可以被写成任何样子**。这就是为什么第 7 章需要一个守门员。

## 4.3 letta-code 怎么把块翻译成文件

创建本地 agent 时，请求体里仍然是 `memory_blocks`（和 Cloud API 保持一致），由 `initialMemoryFilesFromCreateBody()`（`src/backend/local/initial-memory.ts:82`）翻译成初始文件：

```ts
// src/backend/local/initial-memory.ts:41-67（节选）
function renderInitialMemoryFile(input: { label: string; value: string; description?: string | null }) {
  if (input.label === DEFAULT_ROOT_MEMORY_BLOCK.label) {
    return { relativePath: "MEMORY.md", content: input.value };     // 根索引：没有 frontmatter
  }
  const relativePath = rootMemoryBlockPath(input.label);             // "system/persona" → "persona.md"
  if (!validRelativePath(relativePath)) return null;
  const description = typeof input.description === "string" && input.description.trim()
    ? sanitizeFrontmatterValue(input.description)                     // 换行压成空格
    : `Memory block ${input.label}`;
  const frontmatter = ["---", `name: ${memoryNameFromPath(relativePath)}`, `description: ${description}`, "---"];
  return { relativePath, content: [...frontmatter, input.value].join("\n") };
}
```

几个细节：

1. **一个特殊块 `MEMORY`**。`DEFAULT_ROOT_MEMORY_BLOCK`（`src/agent/create-agent-request.ts:44`）的值只是 `"# Memory\n"`。它被翻译成根目录的 `MEMORY.md`——**v2 布局的标志**（第 2 章：有它就是 v2）。如果请求里没带，`initialMemoryFilesFromCreateBody` 会自己补上（“Local agents are always born on the MemFS v2 root layout”）。
2. **路径压平**。`rootMemoryBlockPath()` 去掉 v1 的 `system/` 前缀，再把 `/` 换成 `_`——所有初始块都落在根目录，成为 core memory。
3. **`name` 是推出来的**。`memoryNameFromPath()` 把 `my_persona.md` 变成 `My Persona`。v2 要求每个非索引文件恰好有 `name` 和 `description` 两个 frontmatter 字段。
4. **大小写冲突检测**。macOS 文件系统大小写不敏感，`Persona` 和 `persona` 会撞成同一个文件，所以用 `toLocaleLowerCase("en-US")` 比较并直接报错（`initial-memory.ts:102-109`）。
5. **防路径穿越**。`validRelativePath()` 拒绝绝对路径和 `..` 段——块的 label 来自请求体，不能信任。

生成的文件随后由 `initializeLocalMemoryRepo()`（`src/agent/memory-git.ts:1316`）写入并作为第一个提交（第 6 章）。

## 4.4 mini-letta 的实现

mini-letta v0.2 把 v0.1 的 `blocks` 字段从 `AgentRecord` 里删掉了——块只在**创建时**作为输入，之后的唯一真相是 git 仓库：

```ts
// code/mini-letta @ v0.2  src/memory/memfs.ts
export function initialMemoryFiles(blocks: InitialMemoryBlock[]): MemoryFile[] {
  const links = blocks.map(
    (block) => `- [${block.label}](${block.label}.md) — ${block.description ?? block.label}`,
  );
  const files: MemoryFile[] = [
    { relativePath: "MEMORY.md", content: `${ROOT_MEMORY_INDEX}\n${links.join("\n")}\n` },
  ];
  for (const block of blocks) {
    const description = (block.description ?? `Memory block ${block.label}`).replace(/\r?\n/g, " ");
    files.push({
      relativePath: `${block.label}.md`,
      content: `---\nname: ${titleFromLabel(block.label)}\ndescription: ${description}\n---\n${block.value}\n`,
    });
  }
  return files;
}
```

和 letta-code 的差别：

| | letta-code | mini-letta | 为什么 |
|---|---|---|---|
| 根 `MEMORY.md` 内容 | `# Memory\n` | `# Memory` + 指向每个文件的链接 | 演示“references as synapses”（第 10 章），让索引从第一天起就有用 |
| `system/` 前缀、`/` 压平 | 支持 | 不支持（label 直接当文件名） | mini 不兼容 v1 |
| 大小写冲突 | 检测 | 不检测 | 只在 Linux 上跑；练习题 |

创建出的仓库：

```text
$ export MINI_LETTA_HOME=$(mktemp -d)
$ bun src/cli.ts memory tree
MEMORY.md
human.md
persona.md
$ cat "$(bun src/cli.ts memory path)/persona.md"
---
name: Persona
description: Who I am and how I behave.
---
I am mini-letta, a helpful assistant that remembers.
```

## 4.5 块思维 vs 文件思维

从块到文件，不只是存储格式的变化，还改变了 agent“思考记忆”的方式：

- **块是扁平的**，文件可以有**层次**：`projects/letta-code/MEMORY.md`、`projects/letta-code/architecture.md`……第 5 章的 v2 布局正是利用层次来区分“常驻”和“按需”。
- **块只有文本**，文件可以是**任何东西**：参考 CSV、图片（letta-code 的提示词提到 agent 的头像存在 `$MEMORY_DIR/profile.png`）。
- **块的修改是原子的工具调用**，文件的修改可以是**一系列编辑再一次提交**——提交才是原子单位。这一点在第 6 章会变成整个系统的核心不变量。

有意思的是，letta-code 本地 agent 拿到的系统提示（`letta_local_memfs.md`）至今仍沿用“memory blocks”的说法，而 Cloud 的 `letta_root_memfs.md` 已经改口叫“core memory files”（第 10 章会对比）。概念的迁移往往比代码慢。

## 4.6 练习

1. **巩固**：用 `createAgent({ blocks: [...] })` 创建一个有三个块（`persona`、`human`、`project_conventions`）的 agent，检查生成的 `name` 字段。
2. **扩展**：给 `initialMemoryFiles` 加上大小写冲突检测和路径穿越检测，并写测试（`../evil`、`Human` 与 `human` 同时出现）。
3. **读源码**：`stampRootMemoryOnCreateBody()`（`src/agent/memory-filesystem.ts:167`）和 `prepareRawCreateAgentBodyForMemfs()`（`:196`）为什么要在 Cloud 创建 agent 时**原子地**打上 `git-memory-enabled` 标签并插入根 `MEMORY` 块？注释里说如果不这样做会发生什么？
