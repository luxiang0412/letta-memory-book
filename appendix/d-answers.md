# 附录 D 练习参考答案

> “巩固”题多数是动手观察，这里给出应当看到的现象；“扩展”题给出实现要点；“读源码”题给出答案与依据。

## 第 1 章

1. 两个块（`persona`、`human`）；`<memory_metadata>` 里有 AGENT_ID、CONVERSATION_ID、编译时间、recall 中的消息数（每个回合至少 +2，带工具调用的回合 +4）。
2. 在 `memory_replace` 里：`new_text === ""` 时用 `split("\n").filter(l => !l.includes(old))` 删整行。新风险：agent 可以“遗忘”——误删、被提示注入诱导删除，而且 v0.1 没有历史可以恢复。这正是第 6 章引入 git 的动机之一。
3. 技能通过 `<available_skills>` 列表进入系统提示（本地后端：`appendAvailableSkillsBlock()`，名字来自请求体的 `client_skills`），技能正文按需加载；其他按项目的上下文通过 `<system-reminder>` 注入。

## 第 2 章

1. 见第 2 章 2.1 节的 mini-letta 目录树；补上：`agent.json`（第 1 章，store 写，CLI/loop 读）、`memory/`（第 4 章）、`context.json`（第 12 章，压缩写、loop 读）、`system-prompt.json`（第 9 章）、`pending-reminders.json`（第 9 章，回合后写、回合前读）、`compaction-event.json`（第 12 章写、第 14 章读）、`reflection-state.json`（第 14 章）、`memory-worktrees/`、`reflections/payloads/`、`reflection.lock`（第 15–17 章）。
2. 增加 `format` 参数：v1 时 `normalized.startsWith("system/")`。
3. 子 agent 进程会继承父进程的 `MEMORY_DIR`/`AGENT_ID` 环境变量；如果它被派去处理另一个 agent（或父 agent 的 worktree），环境变量就是错的。运行时上下文是调用方显式设定的作用域，更可信。

## 第 3 章

1. 记忆变化走的是“系统提示不变 + 记录新 revision”的分支：`content` 保留旧值以保住提示缓存，`memfsRevision`、`coreMemory`、`compiledAt` 更新为新值，免得下一步重复生成 `<memory_update>`。
2. 只能在**后面**追加：例如只发增量（变化了的文件），或在 `<memory_update>` 里声明“取代之前所有的 memory_update”。任何修改已有消息的方案都会破坏缓存前缀。
3. 压缩重写了上下文的开头（把一段消息换成摘要），提示缓存的前缀已经失效；此时顺便替换系统提示不会再额外损失缓存。

## Lab 1

1. 加一条规则：匹配 `^忘掉[:：](.+)$`，调用 `memory_replace({label:"human", old_text:"- X", new_text:""})`；测试断言 `human` 块不再包含 X。
2. 在循环里每次调用模型前 `onEvent?.({ type: "step", n: step })`；CLI 打印 `· step n`。
3. 每次 `execute()` 是一“步”：letta-code 的工具（客户端工具）在客户端执行，结果以新的请求发回后端，后端再执行一次。所以本地后端的 `resolveSystemPromptForTurn` 每一步都会被调用。

## 第 4 章

1. `name` 分别是 `Persona`、`Human`、`Project Conventions`（下划线和连字符都被当作分词符）。
2. 检查 `relativePath` 不以 `/` 开头、没有 `.`/`..` 段；用 `toLocaleLowerCase("en-US")` 比较已有路径。
3. 注释说：如果不在创建时原子地打标签、插入根块，Cloud 上的 agent 会“born without GIT_MEMORY_ENABLED_TAG”，此后所有基于标签的检查都会把它当成非 MemFS agent——“on every machine, forever”；原子地做，即使进程中途崩溃，服务器也已经为它初始化了 v2 仓库，后续的惰性同步能把剩下的步骤补齐。

## 第 5 章

1. 删除 `projects/archive/MEMORY.md` 后再提交会被拒：`projects/archive/old.md: missing required index projects/archive/MEMORY.md`。
2. 深度 3（`a/b/c/d.md` 有 3 个目录段），超过 `maxDepth: 2` 被拒：`depth 3 exceeds maxDepth 2`；另外 `projects/archive/2025/MEMORY.md` 也必须存在。
3. 通过上级索引里的普通 Markdown 链接被发现（“references as synapses”）。这是有意的：系统提示只放第一层目录，更深的结构交给索引链，保持常驻部分的大小与目录深度无关。

## 第 6 章

1. `prompt --fresh` 的输出不含改坏的内容；`git stash` 后工作区恢复。
2. 在 `commitMemoryPaths` 里 `try { git commit } catch { git restore --staged -- <paths>; throw }`；测试：写一个缺 frontmatter 的文件，调用后断言抛错且 `git diff --cached --name-only` 为空。
3. 不带路径的 `git commit` 会把暂存区里**所有**东西一起提交，包括 agent 暂存的文件；`git commit -- <paths>` 只提交这些路径。letta-code 的 harness 写者都在 `claimMemoryOperation` 锁内运行，并依赖提示词要求 agent 自己“stage 并在同一条命令里 commit”，从而缩小两者交错的窗口；但主 agent 不走这把锁，所以窗口并非为零。

## 第 7 章

1. 提交配置需要 `MINI_LETTA_CONSTRAINTS_UPDATE=1`；之后 mock 的“设定：”命令会失败，工具结果里是 `persona.md: read-only file cannot be created, changed or removed`，mock 回复“操作失败：…”。
2. 审计通过时记录 `last-valid-revision`；编译时如果 HEAD 审计失败，改为 `git show <last-valid>:<path>`。这并不违背“只认已提交的”——它变成了“只认已提交且有效的”，代价是 HEAD 与生效版本可能不一致，需要在提醒里明说。
3. 技能是一个目录：除了 `SKILL.md` 还有 `scripts/`、`references/`、`templates/`；目录也让技能能被整体移动、删除、弃用，并让 `skills/` 下不会混进普通记忆文件。

## Lab 2

1. `memory show <path>` → `git show HEAD:<path>`。
2. validator 里遍历暂存树，用 `git cat-file -s :<path>` 取大小，超过 1 MB 报错。
3. `.git/hooks` 不会被 clone；CLI 升级后 hook 脚本（以及嵌入的校验函数源码）可能变了，所以在 clone、pull、init 时都重新安装，保证 hook 与当前 CLI 一致。

## 第 8 章

1. 会：`projects/` 出现在 `<deferred-memory>`；`projects/sub/` 不会（只列第一层），要靠 `projects/MEMORY.md` 里的链接发现。
2. 写一个 `escapeXmlAttribute`（`& " ' < >` 五个字符），用于 `path`、`index` 属性。
3. hook 不检查文件名是否是合法的 XML 名称，所以 `<my notes>` 可以出现。模型并不需要严格合法的 XML——这些标签只是给模型看的分节符号——但它会让任何试图用 XML 解析器处理系统提示的工具出错，也让标签边界变得含糊。

## 第 9 章

1. 三条 `<memory_update>`；`recompile` 删除缓存，下一步完整编译，新系统提示含最新记忆，不再产生新的 `<memory_update>`（但旧的三条仍在对话历史里，直到压缩）。
2. 记录上一次 `<memory_update>` 对应的 revision，用 `git diff --name-only <old> <new>` 找出变化的 core 文件，只渲染它们；模型需要拼接多个增量，提示文案里要说明“只包含变化的文件”。
3. 最小改动是让 `<memory_update>` 进入对话存储（例如在 `getOrCompileSystemPrompt` 返回后由后端追加一条持久化消息），这样 `uiMessages` 里就有它；改 pi-stream-adapter 只影响单次请求；改 `persistExecutorStream` 需要区分“模型产生的消息”和“harness 注入的消息”。无论哪种，都要遵守 CLAUDE.md 的“user 角色 + system-reminder”规则。

## 第 10 章

1. 例：“inspect Git status and read the current files before editing”→ 无强制；“stage only the files you changed”→ 无强制（mini 的 mock 遵守）；“commit in the same shell call”→ 无强制；“Verify the committed changes”→ 回合后 `MEMORY COMMIT NEEDED` 提醒是事后反馈。
2. 解析每个 `MEMORY.md` 里的 `](相对路径)`，检查目标存在。放在提醒里更合适：断链不会让记忆“错误”，只会降低可发现性，而 hook 拒绝会挡住所有提交（第 5 章的整树副作用）。
3. 例如本地提示词没有说明根 `MEMORY.md` 不能有 frontmatter、其他文件“恰好 `name` + `description`”、子目录需要索引——而 hook 按这些规则拒绝提交，本地 agent 只能从报错中学。

## Lab 3

1. 修改 `agent.system` 后调用 `resolveSystemPrompt`：返回的 `systemPrompt` 含新文本，`memoryUpdate` 为 `undefined`。
2. 在 `runTurn` 开始处把 `reminders` 通过 `onEvent({type:"reminders", items})` 发出，CLI 打印。
3. 当本地后端启用、或该 agent 启用了 MemFS 时才显示记忆目录（`isLocalBackendEnvEnabled() || settingsManager.isMemfsEnabled(id)`）——非 MemFS 的 agent 没有记忆目录可言。

## 第 11 章

1. 8 192 → 6 554（预留 1 638）；128 000 → 111 616；1 000 000 → 983 616。
2. `complete()` 返回 `usage`，存进 assistant 消息；估算时取最近一条带 usage 的 assistant 消息的值 + 其后消息的估算；压缩时给摘要消息打上时间戳，早于它的 usage 一律忽略。
3. 用户故意设置小 `max_tokens` 时，以 `length` 停止是正常的产品行为，不该触发压缩；如果按 `max_tokens` 算阈值，一个很大的 `max_tokens` 会让 harness 过早压缩，一个很小的又会在上下文真的满了时不压缩。

## 第 12 章

1. `context.json` 里少了被摘要的那些 id，多了一条摘要消息的 id；`messages.jsonl` 只多不少；摘要消息的 `kind` 是 `"summary"`。
2. 把 `estimateMessagesTokens(messages.slice(cutoff)) + floor` 与 `(1 - percentage) * window` 比较；压缩次数减少、每次保留的消息变少，锯齿变缓。
3. `all` 模式下没有“保留最近消息原文”的需要，唯一不能被摘要掉的是还在等结果的工具调用——它的结果马上要追加在后面，调用必须原样在场。

## 第 13 章

1. 两个对话都会命中；分数不同来自 BM25 的长度归一化（短消息分数更高）和词频。
2. 解析引号为短语，候选必须 `includes(phrase)`（CJK 不加空格边界、拉丁文加），命中短语加分。
3. 好处：子 agent 知道父 agent 在做什么，能判断哪些检索结果相关；代价：每次 recall 都要带上父对话的全部上下文 token。`memory` 子 agent 拿到的是“自包含的指令”（描述里要求 “Make the assignment self-contained”），它需要的是记忆文件而不是父对话，所以不分叉，更便宜。

## Lab 4

1. 900 的窗口阈值 720，地板（系统提示 + 工具 + agent-info）约 600，主对话几乎每回合都压缩，但仍能继续。我们实际跑了一下，真正出问题的是**反思**：CLI 让反思子 agent 共用这个 900 的窗口，于是每一次都是 `failed`（第 15 章踩坑记录 3 的同一个循环）。为此 mini-letta 加了 `MINI_LETTA_REFLECTION_CONTEXT_WINDOW`；设为 8000 后同样的场景反思 `merged`。
2. 在 `COMPACTION_EVENT` 里记录被摘要消息的首尾 id；`recall_search` 读取 `context.json`，不在上下文中的命中标注 `(evicted)`。
3. 那个判断是在问“滑动窗口这次压缩是否把上下文压到了窗口以内”，如果还超过整个窗口，下一次请求必然失败，就退回 `all`；而“超过阈值但没超过窗口”可以由下一次请求前的正常检查处理。

## 第 14 章

1. `stepsSinceLastReflection` 每次回合 +1（或 +2，带工具调用时），到 2 时触发；删掉 `reflectedThroughMessageId` 后，下一次反思会从头再看整个对话——重复内容由反思者的“已经记过了吗”过滤掉。
2. 清单 JSON：`{ type: "multi_transcript_reflection_payload", transcripts: [{ conversation_id, mode, payload_path, end_message_id }] }`；收尾时只对 `mode === "unreflected"` 的切片调用 `markReflected`。
3. Cloud 后端的消息在服务器上，客户端每次去拉代价大；客户端 transcript 是本机上已经看到的东西，可以离线、快速、按行切片；`source_message_id` 可能是合成的，说明它是客户端视角的记录，后端未必有一一对应的 id。

## 第 15 章

1. mock 规则：匹配“别再叫我 X 了，叫我 Y”，生成 `sed -i 's/X/Y/' human.md`（或 Edit 工具）而不是追加。
2. 一个模块级 `Map<agentId, { delayMs, retryAt }>`；`parent_dirty`/`merge_conflict` 时 `delayMs = min(prev*2 || 60_000, 30*60_000)`；`launchReflection` 开头检查 `retryAt`，`manual` 触发跳过检查；成功时删除记录。
3. `explicit` 模式让主 agent 在一个“集成对话”里审阅反思分支再自己合并——适用于用户希望 agent 对后台改动“知情并认可”的场景，或需要按 `mergeInstructions` 有选择地合并。`requireAlreadyMerged` 检查反思分支是否确实已经是 HEAD 的祖先：防止集成对话声称合并了、其实没有。

## 第 16 章

1. 返回 `{ launched: false, reason: "parent_dirty" }`。开始时检查是为了不浪费一次反思；收尾时再查，是因为反思可能跑了几分钟，期间主仓库可能变脏。
2. memory worker 是主 agent 主动委派的、针对一个具体请求的改动，合并失败时保留分支让人或模型稍后处理比丢掉更好；反思是周期性的、可以从同一段 transcript 重来的，失败就清理重试最简单。主仓库脏不阻止 worker 合并，因为 git 只在改动重叠时才拒绝，那会表现为冲突。
3. `branch -d` 只删除已合并的分支——在成功路径上，如果分支意外没有被合并，`-d` 会失败而不是丢失提交；失败路径本来就决定丢弃，才用 `-D`。

## 第 17 章

1. 第二个得到 `already_active`；`kill -9` 之后，锁文件里的 pid 已不存在，下一次 `tryAcquireLock` 回收并成功获取。
2. 要点：worktree 标签用 `memory-worker`；合并用 `git merge`，主仓库脏不预先拒绝；冲突时 `merge --abort` 但**不删除**分支，返回分支名供后续处理；合并后同步、使系统提示失效。
3. 要点：在主检出上运行；提示词照搬 `memory.md` 的 Git 一节（读两边、保留意图、不 abort/reset/stash、不清楚就保留现场并报告）；用一个记录文件防止对同一冲突重复启动修复。

## Lab 5

1. 在 `resolveSystemPrompt` 写缓存时已经写进了反思者的对话目录（`agents/<id>~reflection/conversations/reflection-<id>/system-prompt.json`），用 `jq -r .content` 查看，可以看到父 agent 的 `<human>`、`<persona>`。
2. mock 读取任务提示里的 “Additional user-provided reflection instruction”，按关键词过滤候选事实。
3. 崩溃隔离：子进程崩溃不影响主进程，mini 的同进程实现会一起崩；沙箱：letta-code 可以把整个子进程放进沙箱，mini 只能沙箱化 shell 命令、文件工具只靠守卫；`-p` 一次性模式：mini 必须等反思结束才能退出（否则进程退出反思被杀），letta-code 的后台子进程有自己的生命周期管理。

## 第 18 章

1. 冲突提醒里给出了 `git pull --rebase origin main` → 编辑冲突文件 → `git add` → `GIT_EDITOR=true git rebase --continue`。
2. post-commit hook：读 `git config --local mini-letta.memoryRepository.url`；`[ "$branch" = main ] || exit 0`；后台 `git push "$url" main:main >> .git/mirror.log 2>&1 &`。
3. rebase 把别人的提交和自己的提交重新组合成一棵新树，这棵树可能违反约束（比如两边各加了一些内容，合起来超过了核心记忆预算）；推送前要校验的是“将要推上去的那棵树”。

## 第 19 章

1. 只看到 `agent-<自己>`，其他 agent 的目录不存在（tmpfs 覆盖）。
2. validator 里对每个暂存文件做正则匹配；误报可以用一个“需要人类批准”的环境变量放行，或者维护一个允许列表（比如 `.memfs.config.json` 里的 `secretScanAllow` glob，它本身受保护）。
3. letta-code 把记忆子 agent 自己的 agent **目录**（cwd 的直接父目录）挖回为可读，保证进程初始化能沿路径走到 cwd、环境变量得以保留。跨 agent 配置拒绝读取整个 agents 树，如果 cwd 在树里，就会触发这个空环境的坑，所以要求调用方保证 cwd 在树外（主 agent 的 cwd 通常是项目仓库）。

## 第 20 章

1. 在 `conversations()` 里读取 `compaction-event.json` 的 `at` 字段并在页面上显示。
2. `doctor` 命令依次调用：`git status --porcelain`、`auditCommittedMemory`、`memoryTree` 里超过 `maxFileCharacters * 0.8` 的文件、解析 `MEMORY.md` 链接、`conversations()` 里 `stepsSinceReflection > 50` 的对话。
3. 以 SKILL.md 原文为准；一般包括：收集症状、查看当前记忆与系统提示、找出缺失或矛盾、判断是记忆问题还是 harness 问题、做最小修复并验证。Palace 能直接提供“当前记忆”“历史”“对话正在用的系统提示”“压缩与反思状态”这几类证据。

## Lab 6

1. 新服务挂另一个 `data2` 卷和同一个 `remote` 卷，`command: ["bun","src/cli.ts","chat","-a","agent-demo","-p","你知道我什么？"]`；它会从 `remote` 克隆 `agent-demo` 的记忆——前提是 seed 运行时设置了 `MINI_LETTA_REMOTE_ROOT`（compose 里已设置）。
2. 至少需要允许 `unshare`（用户命名空间）和挂载相关的系统调用；放宽容器的 seccomp/能力会削弱容器本身的隔离。多租户场景更常见的做法是每个 agent 一个容器，或在宿主机上用 bwrap，而不是“容器里再套 bwrap”。
3. 静态文件：生成时刻的快照、没有监听端口、打开即用；服务器：数据实时、可部署共享，但多了一个需要保护的网络服务（mini 的 Palace 默认只监听 127.0.0.1、只读、校验 sha 参数）。
