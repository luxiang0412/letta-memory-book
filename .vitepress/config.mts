// VitePress config for a repo-to-book book. Placeholders (__X__) are filled by init_book.sh.
//
// Layout expected:  README.md (becomes the home page) · OUTLINE.md · chapters/*.md · appendix/*.md
//                   chapters/images/* · code/ (companion repo, excluded from the site)
// Sidebar: if .vitepress/sidebar.json exists it defines groups, e.g.
//   [{"text": "Part I 全景", "items": ["01-five-app-forms", "02-dify-architecture"]}, ...]
// (items are file stems under chapters/ or "appendix/<stem>"); otherwise chapters, labs and
// appendix are listed automatically using each file's first "# " heading.
import fs from 'node:fs'
import path from 'node:path'
import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

const ROOT = path.resolve(__dirname, '..')
const GH_USER = 'luxiang0412'
const BOOK_REPO = 'letta-memory-book'
const CODE_REPO = 'mini-letta'

function titleOf(file: string): string {
  const text = fs.readFileSync(file, 'utf8')
  const h1 = text.match(/^#\s+(.+)$/m)?.[1] ?? path.basename(file, '.md')
  // Sidebar text is rendered as HTML: drop code backticks and escape angle brackets
  // (otherwise a title like "缓存、`<memory_update>` 与提醒" loses the tag).
  return h1
    .replace(/^第\s*(\d+)\s*章\s*/, '$1. ')
    .replace(/^Lab\s*(\d+)[：:]\s*/, 'Lab $1 ')
    .replace(/`/g, '')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function link(stem: string) {
  const rel = stem.includes('/') ? stem : `chapters/${stem}`
  return { text: titleOf(path.join(ROOT, `${rel}.md`)), link: `/${rel}` }
}

function sidebar() {
  const custom = path.join(__dirname, 'sidebar.json')
  if (fs.existsSync(custom)) {
    const groups = JSON.parse(fs.readFileSync(custom, 'utf8')) as { text: string; items: string[] }[]
    return groups.map((g) => ({ text: g.text, items: g.items.map(link) }))
  }
  const list = (dir: string) =>
    fs.existsSync(path.join(ROOT, dir))
      ? fs.readdirSync(path.join(ROOT, dir)).filter((f) => f.endsWith('.md')).sort().map((f) => f.slice(0, -3))
      : []
  const chapters = list('chapters')
  return [
    { text: '章节', items: chapters.filter((s) => !s.startsWith('lab-')).map(link) },
    { text: 'Labs', items: chapters.filter((s) => s.startsWith('lab-')).map(link) },
    { text: '附录', items: list('appendix').map((s) => link(`appendix/${s}`)) },
  ].filter((g) => g.items.length)
}

export default withMermaid(
  defineConfig({
    lang: 'zh-CN',
    title: '从 Letta Code 到 Mini-Letta：给 Agent 装上会成长的记忆',
    description: '读 letta-code 记忆子系统源码，从零写一个带 git 记忆、提示编译、上下文压缩和后台反思的 mini agent',
    base: `/${BOOK_REPO}/`,
    cleanUrls: true,
    lastUpdated: true,
    srcExclude: ['code/**', 'node_modules/**', 'scripts/**'],
    rewrites: { 'README.md': 'index.md' },
    ignoreDeadLinks: [/^https?:\/\/localhost/], // books link to local dev servers
    markdown: {
      config: (md) => {
        // Books about template engines are full of `{{...}}`; VitePress compiles markdown as Vue
        // templates, so escape braces in prose and inline code (fenced blocks are already v-pre).
        const esc = (html: string) => html.replace(/\{\{/g, '&#123;&#123;').replace(/\}\}/g, '&#125;&#125;')
        for (const rule of ['text', 'code_inline'] as const) {
          const orig = md.renderer.rules[rule]!
          md.renderer.rules[rule] = (tokens, idx, opts, env, self) => esc(orig(tokens, idx, opts, env, self))
        }
      },
    },
    themeConfig: {
      siteTitle: 'Letta Code → Mini-Letta',
      nav: [
        { text: '开始阅读', link: '/chapters/00-how-to-read' },
        { text: '源码地图', link: '/appendix/a-source-map' },
        { text: '配套代码', link: `https://github.com/${GH_USER}/${CODE_REPO}` },
      ],
      sidebar: sidebar(),
      outline: { level: [2, 3], label: '本页目录' },
      search: { provider: 'local', options: { translations: { button: { buttonText: '搜索', buttonAriaLabel: '搜索' } } } },
      socialLinks: [{ icon: 'github', link: `https://github.com/${GH_USER}/${BOOK_REPO}` }],
      docFooter: { prev: '上一章', next: '下一章' },
      lastUpdated: { text: '最后更新' },
      editLink: { pattern: `https://github.com/${GH_USER}/${BOOK_REPO}/edit/main/:path`, text: '在 GitHub 上编辑此页' },
      footer: { message: `配套代码：github.com/${GH_USER}/${CODE_REPO}`, copyright: '参照 letta-ai/letta-code @ 70ead335' },
    },
  }),
)
