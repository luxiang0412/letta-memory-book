# 第 5 章 MemFS v2 布局：常驻、按需与技能

> 本章目标：掌握 MemFS v2 的目录规则——哪些文件常驻系统提示、哪些只留一个索引、哪些根本不算记忆——以及这些规则为什么能撑起“渐进式披露”。前置：第 4 章。对应代码：mini-letta `v0.2` `src/memory/format.ts`。

## 5.1 问题：常驻的地段很贵

第 1 章说过：常驻系统提示的东西会影响每一个决定，但也占用每一次调用的 token。一个用了半年的 agent 可能积累了几百条项目笔记——全塞进系统提示显然不行，全部不放又会“不知道自己知道”。

解决办法是**渐进式披露（progressive disclosure）**：

- 系统提示里只放**身份、偏好、规则**和**索引**；
- 索引告诉 agent“哪里还有什么”；
- 真正需要时，agent 自己去读。

MemFS v2 用**目录结构**来表达这三层，而不是用额外的元数据。

## 5.2 规则

v2 的规则在系统提示里写得很清楚（`src/agent/prompts/letta_root_memfs.md:28-30`），整理如下：

```text
$MEMORY_DIR/
├── MEMORY.md              根索引，无 frontmatter          → 常驻（<memory> 段）
├── persona.md             根目录的其他 .md                → 常驻（core memory）
├── human.md               恰好 name + description
├── projects/
│   ├── MEMORY.md          子目录索引，无 frontmatter       → 只列出目录（<deferred-memory>）
│   ├── letta-code.md      恰好 name + description          → 按需读取
│   └── archive/
│       ├── MEMORY.md      更深一层的索引
│       └── 2025.md
├── notes/
│   └── idea.md            notes/ 没有 MEMORY.md            → ✗ 提交被拒
├── skills/
│   └── release-notes/
│       └── SKILL.md       技能自己的 frontmatter           → 不是“记忆”，单独管理
└── profile.png            非 Markdown 文件                → 普通文件，随仓库同步
```

一句话版本：**根目录 = 常驻；有 `MEMORY.md` 的子目录 = 按需；`skills/` = 技能；其余 Markdown = 不允许。**

## 5.3 letta-code 怎么判定

两条规则都在 `src/agent/memory-format.ts` 里，非常短：

```ts
// src/agent/memory-format.ts:13-21
export function isCoreMemoryPath(relativePath: string, format: LocalMemoryFormat): boolean {
  const normalized = relativePath.replace(/\\/g, "/");
  if (!normalized.endsWith(".md")) return false;
  if (format === "memfs-v2") return !normalized.includes("/");   // v2：根目录
  return normalized.startsWith("system/");                       // v1：system/ 目录
}
```

```ts
// src/agent/memory-format.ts:23-41
export function isProjectedMemoryPath(relativePath: string, allPaths: ReadonlySet<string>,
                                      format: LocalMemoryFormat): boolean {
  const normalized = relativePath.replace(/\\/g, "/");
  if (format === "memfs-v1") return true;
  if (normalized === "skills" || normalized.startsWith("skills/")) return false;
  if (!normalized.includes("/")) return true;
  const parts = normalized.split("/");
  const directories = parts.slice(0, -1);
  let current = "";
  for (const directory of directories) {
    current = current ? `${current}/${directory}` : directory;
    if (!allPaths.has(`${current}/MEMORY.md`)) return false;      // 每一级祖先都要有索引
  }
  return true;
}
```

“projected”（被投影）这个词值得注意：letta-code 把 MemFS 看作记忆的一个**投影**——记忆本身是 agent 的上下文，文件系统只是它的一种表示（系统提示原文，`letta_root_memfs.md:19`：“Memory files and external memory are *projected* to a local memory filesystem (MemFS)”）。`isProjectedMemoryPath` 回答的是：“这个文件是不是记忆的一部分”。

注意 `isProjectedMemoryPath` 要求**每一级**祖先目录都有 `MEMORY.md`。`projects/archive/2025.md` 要被承认，`projects/MEMORY.md` 和 `projects/archive/MEMORY.md` 都必须存在。索引链断了，下面的东西就“不存在”。

## 5.4 规则在哪里被强制

规则写在系统提示里只是“建议”。真正强制的是 git hook 里的两道检查（第 7 章细讲），这里先看效果：

1. **frontmatter 检查**只对“被投影”的路径做（`src/agent/memory-git-hooks.ts:96-109` 那段循环里，`root-marker` 策略会跳过不在索引链上的路径）；
2. **树约束检查**（`src/memory-constraints.ts:61-73`）对所有非 `skills/` 的 `.md` 要求索引链完整：

```ts
// src/memory-constraints.ts:61-73（节选）
if (v2) {
  for (const { path } of memoryFiles) {
    const directories = path.split("/").slice(0, -1);
    let current = "";
    for (const directory of directories) {
      current = current ? `${current}/${directory}` : directory;
      const index = `${current}/MEMORY.md`;
      if (!paths.has(index)) {
        errors.push(`${path}: missing required index ${index}`);
        break;
      }
    }
  }
}
```

所以“不在索引链上的 Markdown”在 v2 里不是“被忽略”，而是**根本提交不进去**。这逼着 agent 每建一个新目录，就先写它的索引。

hook 用哪套规则，取决于 git 公共目录里一个叫 `letta-memory-layout-policy` 的文件（`memory-git-hooks.ts:21`）：根目录有 `MEMORY.md` 就写入 `root-marker`（`memory-git-hooks.ts:224-234`），否则 `legacy-only`；共享记忆仓库用 `shared-memory`。

## 5.5 技能为什么单独放

`skills/<name>/SKILL.md` 是**程序性记忆**：不是“我知道什么”，而是“这件事怎么做”。它有自己的 frontmatter 格式（`name`、`description`，描述以 “This skill should be used when…” 开头，可能还有 `version`），目录里还可以有 `scripts/`、`references/`、`templates/`。

它和记忆分开的原因：

- **加载方式不同**：技能的名字和描述以 `<available_skills>` 列表进入上下文（`src/backend/local/system-prompt-compilation.ts:391` 的 `compileAvailableSkillsBlock()`），正文在需要时才加载；
- **格式校验不同**：hook 显式跳过 `skills/`（`isProjectedMemoryPath` 第一行就排除了它），但会拒绝扁平的 `skills/foo.md`——技能必须是目录（hook 里那句 “invalid skill path (skills must be folders)”）。

## 5.6 mini-letta 的实现与验证

mini-letta 只实现 v2，所以两个函数更短：

```ts
// code/mini-letta @ v0.2  src/memory/format.ts
export function isCoreMemoryPath(relativePath: string): boolean {
  const normalized = normalizeMemoryPath(relativePath);
  return normalized.endsWith(".md") && !normalized.includes("/");
}

export function isProjectedMemoryPath(relativePath: string, allPaths: ReadonlySet<string>): boolean {
  const normalized = normalizeMemoryPath(relativePath);
  if (normalized === "skills" || normalized.startsWith("skills/")) return false;
  if (!normalized.includes("/")) return true;
  const directories = normalized.split("/").slice(0, -1);
  let current = "";
  for (const directory of directories) {
    current = current ? `${current}/${directory}` : directory;
    if (!allPaths.has(`${current}/MEMORY.md`)) return false;
  }
  return true;
}
```

测试（`test/v02-memfs.test.ts`）：

```ts
const all = new Set(["MEMORY.md", "human.md", "projects/MEMORY.md", "projects/a.md", "notes/b.md", "skills/x/SKILL.md"]);
expect(isCoreMemoryPath("human.md")).toBe(true);
expect(isProjectedMemoryPath("projects/a.md", all)).toBe(true);
expect(isProjectedMemoryPath("notes/b.md", all)).toBe(false);
expect(isProjectedMemoryPath("skills/x/SKILL.md", all)).toBe(false);
```

在真实仓库里试一下“没有索引的目录”：

```text
$ D=$(bun src/cli.ts memory path) && cd $D
$ mkdir notes && printf -- '---\nname: B\ndescription: a note\n---\nhello\n' > notes/b.md
$ git add notes && git commit -qm "add note"
Memory validation failed:
  notes/b.md: missing required index notes/MEMORY.md
$ mkdir -p skills/x && printf -- '---\nname: x\ndescription: This skill should be used when testing.\n---\n' > skills/x/SKILL.md
$ git add skills && git commit -qm "add skill"
Memory validation failed:
  notes/b.md: missing required index notes/MEMORY.md
$ printf '# Notes\n' > notes/MEMORY.md && git add notes && git commit -qm "index notes"
$ git log --oneline
1d8ebf7 index notes
2bc93f0 chore: initialize local memory
```

第二次提交（只想加一个技能）**也失败了**——因为 `notes/b.md` 还留在暂存区里，而 v2 的校验检查的是**整棵暂存树**，不只是这次改动的文件。第三次提交补上索引后，暂存区里所有东西（包括那个技能）一起进去了。这是“整树校验”的一个真实副作用：一个坏文件会挡住所有后续提交，直到被修好或移出暂存区。letta-code 的约束校验器在报错时专门加了一句提醒（`src/agent/memory-constraints.ts:101`）：“Validation checks the complete repository, so these problems may predate your staged changes.”

## 5.7 v2 布局在系统提示里长什么样

第 8 章才写编译器，这里先看 v0.3 编译出来的样子（三个根文件 + 一个带索引的子目录 + 一个技能）：

```text
<human>
<description>The user</description>
- likes pnpm
</human>

<memory>
# Memory
- [projects](projects/MEMORY.md)
<deferred-memory>
<directory path="projects/" index="projects/MEMORY.md" />
</deferred-memory>
</memory>
```

子目录只以一行 `<directory .../>` 出现；`projects/letta-code.md` 的正文、甚至它的名字，都不在系统提示里。agent 想知道 `projects/` 下有什么，就去读 `projects/MEMORY.md`。技能不在这里出现，它走 `<available_skills>`。

## 5.8 设计取舍

- **用目录而不是标签区分层级**：好处是人和 agent 都能一眼看懂、`mv` 一下就能“降级/升级”一个文件（反思子 agent 的提示词原话：“You can also move files between root and child directories to change their tier”，`src/agent/subagents/builtin/reflection-v2.md:47`）；代价是规则藏在路径里，必须有 hook 来强制。
- **强制索引**：保证每一块按需记忆都“可被发现”，代价是每建一个目录都多一个文件。
- **`MEMORY.md` 不带 frontmatter**：索引本身就是内容，不需要“描述的描述”。

## 5.9 练习

1. **巩固**：在 mini-letta 的记忆仓库里建立 `projects/MEMORY.md`、`projects/mini-letta.md`、`projects/archive/MEMORY.md`、`projects/archive/old.md`，提交成功后，`git rm projects/archive/MEMORY.md` 再提交，会发生什么？
2. **扩展**：v2 默认 `maxDepth: 2`（`src/memory-constraints.ts:302-308`）。`projects/archive/2025/q1.md` 的深度是几？会被拒吗？用 mini-letta 验证。
3. **读源码**：`renderRootMemoryProjection()`（`src/backend/local/system-prompt-compilation.ts:154`）只把**第一层**子目录的索引列进 `<deferred-memory>`（正则 `^[^/]+\/MEMORY\.md$`）。更深的目录怎么被发现？这是有意的吗？
