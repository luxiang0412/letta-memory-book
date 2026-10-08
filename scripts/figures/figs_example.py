"""Example figures showing the helper API. Copy this file to figs_<topic>.py and replace.

Conventions used in the Dify book:
- one figure = one mechanism; title (bold) + one-line subtitle at top-left
- tones: accent (the thing under discussion), ok/warn/bad (state), purple/teal (secondary actors), muted (inactive)
- every arrow that carries meaning gets a short label; long explanations go in the markdown caption
- the Fig label (first arg) doubles as the aria-label/title: state the figure's claim in one sentence
"""

from svg import MUTED, Fig


def fig_request_flow() -> Fig:
    f = Fig(860, 300, "一次请求的路径：浏览器请求 API，API 把任务交给工作线程，工作线程执行后把事件经队列推回 API，再以 SSE 流回浏览器。")
    f.title("示例：一次请求的路径", "替换成你要讲的机制")
    f.box(30, 110, 150, 60, "浏览器", "fetch + SSE", tone="neutral")
    f.box(260, 110, 170, 60, "API", "prepare → subscribe", tone="accent")
    f.box(520, 70, 170, 50, "队列", "job / events", tone="purple", size=12)
    f.box(520, 170, 170, 60, "工作线程", "执行引擎", tone="neutral")
    f.arrow([(180, 130), (260, 130)], "POST /run")
    f.arrow([(260, 155), (180, 155)], "SSE", tone="accent", label_dy=16)
    f.arrow([(430, 125), (520, 95)], "job")
    f.arrow([(605, 120), (605, 170)], "取出", label_dx=18, label_dy=4)
    f.arrow([(520, 210), (470, 210), (470, 150), (430, 150)], "事件", tone="purple", dashed=True, label_at=0.15, label_dy=-8)
    f.text(430, 280, "图注写在 markdown 里；图内只放短标签。", size=12, color=MUTED)
    return f


def _mini_state(f: Fig, ox: int, oy: int, done: set[str], step: str) -> None:
    """Small-multiples helper: the same tiny graph drawn at several moments."""
    nodes = {"A": (ox, oy), "B": (ox + 90, oy), "C": (ox + 180, oy)}  # group spans 240px
    for a, b in [("A", "B"), ("B", "C")]:
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        f.arrow([(x1 + 60, y1 + 15), (x2, y2 + 15)], tone="ok" if a in done else "neutral")
    for n, (x, y) in nodes.items():
        f.box(x, y, 60, 30, n, tone="ok" if n in done else "neutral", size=12)
    f.text(ox, oy - 10, step, size=12, anchor="start", weight="700")


def fig_small_multiples() -> Fig:
    f = Fig(860, 200, "小多图示例：同一张图在三个时刻的状态，用来讲状态随时间的变化。")
    f.title("示例：小多图（small multiples）", None)
    _mini_state(f, 30, 110, set(), "① 开始")
    _mini_state(f, 310, 110, {"A"}, "② A 完成")
    _mini_state(f, 590, 110, {"A", "B"}, "③ B 完成")
    return f


FIGS = {
    "fig-00-example-flow": fig_request_flow,
    "fig-00-example-small-multiples": fig_small_multiples,
}
