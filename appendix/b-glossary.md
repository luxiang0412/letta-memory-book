# 附录 B 术语表

| 术语 | 含义 | 章节 |
|---|---|---|
| agent | 一个有身份（id）、有记忆的长期存在的智能体；对话是它和外界的一次次交互 | 1 |
| harness | 包在模型外面的程序：拼上下文、执行工具、存储与整理记忆。letta-code 就是一个 harness | 0 |
| 回合（turn） | 用户发一条消息，到 agent 给出不带工具调用的回复为止 | Lab 1 |
| 步（step） | 回合中的一次模型调用。反思的 step-count 触发器数的是 assistant 步 | 14 |
| core memory（核心记忆） | 常驻系统提示的记忆；v2 中即根目录下的 Markdown 文件 | 1、5 |
| memory block（记忆块） | MemGPT/Letta 服务器中的核心记忆单元：label、value、description、limit、read_only | 4 |
| MemFS | 记忆文件系统：一个 git 仓库，里面是 Markdown 记忆文件、技能与其他文件 | 2 |
| v1 / v2 布局 | v1：core 在 `system/`；v2：core 在根目录，根目录有 `MEMORY.md` | 2、5 |
| `MEMORY.md` | 无 frontmatter 的索引文件；根索引进入系统提示，子目录索引使该目录成为记忆 | 5 |
| deferred memory（延迟/按需记忆） | 带索引的子目录里的文件；系统提示中只有目录条目 | 5、8 |
| 投影（projection） | 记忆在文件系统上的表示；`isProjectedMemoryPath` 判断文件是否属于记忆 | 5 |
| skill（技能） | `skills/<name>/SKILL.md`，程序性记忆，按需加载 | 5 |
| recall memory | 全部历史消息；只追加，可检索，不可修改 | 1、13 |
| frontmatter | 文件开头 `---` 包围的元数据；v2 要求恰好 `name` 和 `description` | 7 |
| pre-commit hook | git 提交前运行的脚本；记忆仓库用它校验格式和预算 | 7 |
| `.memfs.config.json` | 预算与约束配置；本身受保护，修改需要人类批准 | 7 |
| 审计（audit） | 用临时索引校验已提交的 HEAD，防 hook 被绕过 | 7 |
| 编译（compile） | 把已提交的记忆渲染成文本并替换系统提示中的 `{CORE_MEMORY}` | 8 |
| `{CORE_MEMORY}` | 系统提示里记忆的插入点 | 8 |
| memfsRevision | 编译时记忆仓库 HEAD 的提交号 | 9 |
| rawSystemHash | 原始系统提示（未注入记忆）的 sha256 | 9 |
| `<memory_update>` | 对话中途记忆变化时追加给模型的新记忆全文；系统提示保持不变 | 3、9 |
| prompt caching（提示缓存） | 服务商按请求前缀缓存；系统提示一变，缓存全部失效 | 9 |
| `<system-reminder>` | harness 发给模型的自动通知，以 user 角色消息承载 | 9 |
| agent-info | 每个对话首条消息附带的提醒：agent id、记忆目录等 | 9 |
| 地板（floor） | 系统提示 + 工具定义的 token 数，每次请求都要付 | 11 |
| compaction（压缩） | 用一条摘要替换上下文开头的一段消息 | 12 |
| sliding window（滑动窗口） | 只摘要最前面一部分、保留最近消息的压缩模式 | 12 |
| `in_context_message_ids` | 当前在上下文窗口里的消息 id 列表 | 12 |
| summary_message | 压缩摘要消息的类型；存储上是 user 角色 | 12、13 |
| BM25 | 经典的文本相关性排序公式（k1、b 两个参数） | 13 |
| 检索回声（search echo） | 历史中的检索调用、检索结果、以及正在问的问题本身；需要降权 | 13 |
| reflection / sleeptime / dream | 对话之间在后台回顾经历、整理记忆的子 agent | 14、15 |
| compaction-event / step-count | 反思的两种自动触发器 | 14 |
| 水位线（watermark） | `reflected_through_message_id`：反思到了哪条消息 | 14 |
| payload | 交给反思子 agent 的 transcript 切片文件（`$TRANSCRIPT_PATH`） | 15 |
| worktree | 同一 git 仓库的另一个检出；反思和 worker 在其中工作 | 16 |
| merged / no_changes / parent_dirty / merge_conflict / dirty_uncommitted / failed | 反思收尾的六种状态；只有前两种消费 transcript | 16 |
| memory operation lease（记忆操作锁） | 串行化 harness 自己的记忆写者的文件锁；持有者死亡才回收 | 17 |
| memory worker | 主 agent 委派的后台记忆更新子 agent | 17 |
| conflict repair | 同步冲突或校验失败后启动的修复子 agent | 17 |
| remoteMemfs / localMemfs | 后端能力：记忆仓库在服务器上 / 在本机 | 2、18 |
| cross-agent guard | 进程内文件工具的跨 agent 路径检查（字面 + realpath） | 19 |
| bwrap（bubblewrap） | Linux 上用挂载命名空间实现的沙箱 | 19 |
| Seatbelt | macOS 的沙箱机制（`sandbox-exec`） | 19 |
| Memory Palace | 记忆的只读可视化页面（`/palace`） | 20 |
| `/doctor` | 用观察到的行为作证据、诊断并修复上下文的流程 | 20 |
