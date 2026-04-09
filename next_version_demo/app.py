"""Council Demo — DOS-style TUI for multi-model autonomous research."""

import asyncio
import random
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.screen import ModalScreen
from textual.widgets import (
    Header, Footer, Static, ListView, ListItem, RichLog, Input, Button, Label,
)
from textual.reactive import reactive
from textual import on

from next_version_demo.data import (
    EXPERIMENTS, MODELS, PROPOSALS_ROUND, CRITIQUES, VOTES, FAKE_CHAT_RESPONSES,
)


class ExperimentItem(ListItem):
    def __init__(self, exp: dict) -> None:
        self.exp = exp
        super().__init__()

    def compose(self) -> ComposeResult:
        score = self.exp["score"]
        title = self.exp["title"][:40]
        status = self.exp["status"]
        if status == "best":
            yield Static(f"[bold green]★ {score:.0f}[/] {title}")
        elif status == "keep":
            yield Static(f"[green]  {score:.0f}[/] [dim]{title}[/]")
        else:
            yield Static(f"[dim]  {score:.0f} {title}[/]")


class ProposalWidget(Static):
    def __init__(self, proposal: dict) -> None:
        self.proposal = proposal
        content = (
            f"[bold cyan]#{proposal['id']}[/] [bold]{proposal['title']}[/]\n"
            f"[dim]{proposal['desc'][:150]}...[/]\n"
            f"Impact: [{'green' if proposal['impact'] == 'large' else 'yellow'}]{proposal['impact']}[/]"
        )
        super().__init__(content)


class QueueItem(Static):
    def __init__(self, phase: str, detail: str, status: str = "pending") -> None:
        icon = {"pending": "○", "running": "◉", "done": "●"}[status]
        color = {"pending": "dim", "running": "bold yellow", "done": "green"}[status]
        super().__init__(f"[{color}]{icon} {phase:14s}[/] [{color}]{detail}[/]")


class ChatScreen(ModalScreen):
    """Modal chat with the council agents."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-modal"):
            yield Static("[bold cyan]Chat with the Council[/]\n[dim]Propose ideas, ask questions, discuss strategies[/]", id="chat-header")
            yield RichLog(id="chat-log", wrap=True, markup=True)
            yield Input(placeholder="Type your idea or question...", id="chat-input")
            yield Static("[dim]Press Escape to close[/]", id="chat-hint")

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold cyan]Council:[/] Welcome! I'm the council of models. What would you like to explore?")
        log.write("")

    @on(Input.Submitted, "#chat-input")
    def on_chat_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        log = self.query_one("#chat-log", RichLog)
        inp = self.query_one("#chat-input", Input)
        log.write(f"\n[bold white]You:[/] {text}")
        # Fake response
        resp = random.choice(FAKE_CHAT_RESPONSES)
        model = random.choice(MODELS)
        log.write(f"\n[bold {model['color']}]{model['id']}:[/] {resp}")
        inp.value = ""


class DeepResearchScreen(ModalScreen):
    """Modal showing the deep research prompt."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="research-modal"):
            yield Static("[bold magenta]Deep Research Prompt[/]\n[dim]Copy this into ChatGPT Deep Research / Perplexity[/]", id="research-header")
            yield RichLog(id="research-log", wrap=True, markup=True)
            yield Static("[dim]Press Escape to close[/]")

    def on_mount(self) -> None:
        log = self.query_one("#research-log", RichLog)
        log.write("[bold yellow]── Problem ──[/]")
        log.write("AMM Fee Strategy Optimization — maximize edge score")
        log.write("")
        log.write("[bold yellow]── Current State ──[/]")
        best = max(EXPERIMENTS, key=lambda e: e["score"])
        log.write(f"Best score: [bold green]{best['score']:.2f}[/] ({best['title']})")
        log.write(f"Experiments tried: {len(EXPERIMENTS)}")
        log.write(f"Target: ~522 (leaderboard)")
        log.write("")
        log.write("[bold yellow]── Experiments Tried ──[/]")
        for exp in EXPERIMENTS:
            log.write(f"  [cyan]{exp['branch']}[/] = {exp['score']:.0f}")
        log.write("")
        log.write("[bold yellow]── Research Questions ──[/]")
        log.write("• What does academic literature say about optimal CFMM fees?")
        log.write("• What strategies won similar competitions?")
        log.write("• What approaches from market microstructure apply here?")
        log.write("• What am I missing — why is there a 128-point gap to leaders?")


class CouncilDemo(App):
    """Multi-model autonomous research demo."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main {
        height: 1fr;
    }

    #left-panel {
        width: 30;
        border: solid $primary;
        padding: 0 1;
    }

    #left-panel-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        padding: 0 0 1 0;
    }

    #middle-panel {
        width: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }

    #middle-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        padding: 0 0 1 0;
    }

    #right-panel {
        width: 38;
        border: solid $primary;
        padding: 0 1;
    }

    #right-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        padding: 0 0 1 0;
    }

    #queue-container {
        height: 1fr;
    }

    #middle-log {
        height: 1fr;
    }

    #model-stats {
        height: auto;
    }

    #buttons {
        height: 3;
        align: center middle;
        dock: bottom;
    }

    Button {
        margin: 0 1;
        min-width: 14;
    }

    #chat-modal, #research-modal {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #chat-header, #research-header {
        height: 3;
    }

    #chat-log, #research-log {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    #chat-input {
        height: 3;
    }

    #chat-hint {
        height: 1;
    }

    QueueItem {
        height: 1;
    }

    ProposalWidget {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        border: solid $primary-lighten-2;
    }

    ExperimentItem {
        height: 1;
    }
    """

    TITLE = "Auto Research with Council"
    SUB_TITLE = "Multi-Model Autonomous Research"

    BINDINGS = [
        Binding("c", "open_chat", "Chat"),
        Binding("r", "open_research", "Research"),
        Binding("space", "advance", "Next Step"),
        Binding("a", "auto_run", "Auto Run"),
        Binding("q", "quit", "Quit"),
    ]

    phase_index = reactive(0)
    auto_running = reactive(False)

    PHASES = [
        ("CONTEXT", "Loading challenge state..."),
        ("PROPOSE", "4 models generating ideas..."),
        ("PROPOSE_DONE", "9 proposals received"),
        ("CRITIQUE", "4 models reviewing proposals..."),
        ("CRITIQUE_DONE", "Critiques complete"),
        ("PROPOSE_2", "Revised proposals after critiques..."),
        ("PROPOSE_2_DONE", "6 new proposals"),
        ("CRITIQUE_2", "Second round of review..."),
        ("CRITIQUE_2_DONE", "All critiques in"),
        ("VOTE", "Models scoring 0-100..."),
        ("VOTE_DONE", "Winner selected"),
        ("IMPLEMENT", "Claude Code implementing..."),
        ("IMPLEMENT_DONE", "Compiled + validated"),
        ("TEST", "Running 1000 simulations..."),
        ("SCORE", "Score: 398.42"),
        ("RECORD", "exp/398-confidence-gated-asymmetry"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield Static("[bold]Experiments[/]", id="left-panel-title")
                yield ListView(
                    *[ExperimentItem(exp) for exp in EXPERIMENTS],
                    id="experiment-list",
                )
                yield Static("", id="model-stats")
            with Vertical(id="middle-panel"):
                yield Static("[bold]Council Deliberation[/]", id="middle-title")
                yield RichLog(id="middle-log", wrap=True, markup=True)
            with Vertical(id="right-panel"):
                yield Static("[bold]Run Queue[/]", id="right-title")
                yield Container(id="queue-container")
                with Horizontal(id="buttons"):
                    yield Button("Chat [c]", id="btn-chat", variant="primary")
                    yield Button("Research [r]", id="btn-research", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._update_model_stats()
        self._update_queue()
        log = self.query_one("#middle-log", RichLog)
        log.write(f"[bold cyan]{'═' * 50}[/]")
        log.write(f"  [bold]COUNCIL ROUND 8[/]  |  Best: [bold green]394.06[/]")
        log.write(f"[bold cyan]{'═' * 50}[/]")
        log.write("")
        log.write("[dim]Press [bold]Space[/] to advance, [bold]A[/] for auto-run, [bold]C[/] to chat, [bold]R[/] for research[/]")
        log.write("")

    def _update_model_stats(self) -> None:
        stats = self.query_one("#model-stats", Static)
        lines = ["\n[bold]Model Wins[/]"]
        for m in sorted(MODELS, key=lambda x: -x["wins"]):
            bar = "█" * m["wins"] + "░" * (5 - m["wins"])
            lines.append(f"[{m['color']}]{bar}[/] {m['id'].split('/')[-1][:12]} ({m['wins']})")
        stats.update("\n".join(lines))

    def _update_queue(self) -> None:
        container = self.query_one("#queue-container")
        container.remove_children()
        for i, (phase, detail) in enumerate(self.PHASES):
            if i < self.phase_index:
                status = "done"
            elif i == self.phase_index:
                status = "running"
            else:
                status = "pending"
            container.mount(QueueItem(phase, detail, status))

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    async def _advance_phase(self) -> None:
        if self.phase_index >= len(self.PHASES):
            return

        log = self.query_one("#middle-log", RichLog)
        phase, detail = self.PHASES[self.phase_index]
        ts = self._ts()

        if phase == "CONTEXT":
            log.write(f"[dim]{ts}[/] [bold magenta]CONTEXT[/]  Loading challenge state")
            log.write(f"           Target: [bold]strategy.sol[/]")
            log.write(f"           Past experiments: [bold]7[/]")
            log.write(f"           Best: [bold green]394.06[/] (exp/394-hazard-pulse)")
            log.write(f"           Research findings: [bold magenta]loaded[/]")
            log.write(f"           Context: 31,235 chars")

        elif phase == "PROPOSE":
            log.write(f"\n[dim]{ts}[/] [bold magenta]PROPOSE[/]  4 models x 3 ideas")
            log.write(f"[dim]{ts}[/] [bold magenta]PROMPT → PROPOSE[/]  [dim](31,834 chars)[/]")
            log.write(f"  [bold yellow]─── Experiment History ───[/]")
            for exp in EXPERIMENTS[-4:]:
                log.write(f"  [cyan]=== {exp['branch']} ===[/]")
            log.write(f"  [bold yellow]─── Your Task ───[/]")
            log.write(f"  [dim]You are one member of a research committee...[/]")

        elif phase == "PROPOSE_DONE":
            for m in MODELS:
                t = random.uniform(15, 80)
                log.write(f"  [dim]{self._ts()}[/] [green]✓[/] [bold]{m['id']:20s}[/] 3 ideas [dim]({t:.1f}s)[/]")
            log.write("")
            for p in PROPOSALS_ROUND[:4]:
                color = "green" if p["impact"] == "large" else "yellow"
                log.write(f"  [bold cyan]#{p['id']}[/] [bold]{p['title']}[/]")
                log.write(f"     [dim]{p['desc'][:100]}...[/]")
                log.write(f"     Impact: [{color}]{p['impact']}[/]")

        elif phase == "CRITIQUE":
            log.write(f"\n[dim]{ts}[/] [bold magenta]CRITIQUE[/]  4 models reviewing 6 proposals")

        elif phase == "CRITIQUE_DONE":
            for m in MODELS:
                t = random.uniform(20, 60)
                log.write(f"  [dim]{self._ts()}[/] [green]✓[/] [bold]{m['id']:20s}[/] 6 critiques [dim]({t:.1f}s)[/]")
            for c in CRITIQUES[:4]:
                log.write(f"  [dim]Critique on #{c['proposal_id']}:[/]")
                log.write(f"     [green]+[/] {c['strength'][:80]}")
                log.write(f"     [red]-[/] {c['weakness'][:80]}")

        elif phase == "PROPOSE_2":
            log.write(f"\n[dim]{ts}[/] [bold magenta]PROPOSE 2[/]  4 models (informed by critiques)")

        elif phase == "PROPOSE_2_DONE":
            for m in MODELS:
                t = random.uniform(15, 50)
                log.write(f"  [dim]{self._ts()}[/] [green]✓[/] [bold]{m['id']:20s}[/] 3 ideas [dim]({t:.1f}s)[/]")

        elif phase == "CRITIQUE_2":
            log.write(f"\n[dim]{ts}[/] [bold magenta]CRITIQUE 2[/]  4 models reviewing 12 proposals")

        elif phase == "CRITIQUE_2_DONE":
            for m in MODELS:
                t = random.uniform(30, 70)
                log.write(f"  [dim]{self._ts()}[/] [green]✓[/] [bold]{m['id']:20s}[/] 12 critiques [dim]({t:.1f}s)[/]")

        elif phase == "VOTE":
            log.write(f"\n[dim]{ts}[/] [bold magenta]VOTE[/]  4 models scoring 12 proposals (0-100)")

        elif phase == "VOTE_DONE":
            for m in MODELS:
                t = random.uniform(5, 20)
                log.write(f"  [dim]{self._ts()}[/] [green]✓[/] [bold]{m['id']:20s}[/] voted [dim]({t:.1f}s)[/]")
            log.write("")
            sorted_votes = sorted(VOTES, key=lambda v: -v["total"])
            for i, v in enumerate(sorted_votes[:5]):
                prop = next(p for p in PROPOSALS_ROUND if p["id"] == v["proposal_id"])
                pct = v["total"] / 400 * 100
                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                color = "green" if i == 0 else "yellow" if i <= 2 else "dim"
                log.write(f"  [{color}]#{i+1}[/]  {bar}  [bold]{v['total']}/400[/]  {prop['title']}")

        elif phase == "IMPLEMENT":
            log.write(f"\n[dim]{ts}[/] [bold cyan]IMPLEMENT[/]  Claude Code working on: [bold]\"Confidence-gated wide asymmetry\"[/]")
            log.write(f"[dim]{'─' * 50}[/]")
            log.write(f"  [blue]Reading: strategy.sol[/]")
            log.write(f"  [yellow]Editing: strategy.sol[/]")
            log.write(f"  [cyan]$ uv run amm-match validate strategy.sol[/]")

        elif phase == "IMPLEMENT_DONE":
            log.write(f"  [green]✓ Compiled  ✓ Validated[/]")
            log.write(f"[dim]{'─' * 50}[/]")

        elif phase == "TEST":
            log.write(f"\n[dim]{ts}[/] [bold magenta]TEST[/]  uv run amm-match run strategy.sol")
            log.write(f"  Running 1000 simulations...")

        elif phase == "SCORE":
            new_score = 398.42
            log.write(f"  [dim]{self._ts()}[/] Score: [bold green]{new_score}[/] [on green] NEW BEST [/]")

        elif phase == "RECORD":
            log.write(f"\n[dim]{self._ts()}[/] [bold cyan]RECORD[/] → [bold]exp/398-confidence-gated-asymmetry[/]")
            log.write(f"           Proposed by: [bold]gpt-5.4[/]")
            log.write("")
            log.write(f"[bold cyan]{'═' * 50}[/]")
            log.write(f"  [bold]COUNCIL ROUND 9[/]  |  Best: [bold green]398.42[/]")
            log.write(f"[bold cyan]{'═' * 50}[/]")
            # Add to experiments list
            new_exp = {"branch": "exp/398-confidence-gated", "score": 398.42,
                       "title": "Confidence-gated wide asymmetry", "proposer": "gpt-5.4", "status": "best"}
            # Update old best
            for exp in EXPERIMENTS:
                if exp["status"] == "best":
                    exp["status"] = "keep"
            EXPERIMENTS.append(new_exp)
            exp_list = self.query_one("#experiment-list", ListView)
            exp_list.append(ExperimentItem(new_exp))

        self.phase_index += 1
        self._update_queue()

    def action_advance(self) -> None:
        if self.phase_index < len(self.PHASES):
            asyncio.ensure_future(self._advance_phase())

    async def _auto_run_loop(self) -> None:
        self.auto_running = True
        while self.auto_running and self.phase_index < len(self.PHASES):
            await self._advance_phase()
            delay = random.uniform(0.8, 2.5)
            await asyncio.sleep(delay)
        self.auto_running = False

    def action_auto_run(self) -> None:
        if self.auto_running:
            self.auto_running = False
        else:
            asyncio.ensure_future(self._auto_run_loop())

    def action_open_chat(self) -> None:
        self.push_screen(ChatScreen())

    def action_open_research(self) -> None:
        self.push_screen(DeepResearchScreen())

    @on(Button.Pressed, "#btn-chat")
    def on_chat_button(self) -> None:
        self.push_screen(ChatScreen())

    @on(Button.Pressed, "#btn-research")
    def on_research_button(self) -> None:
        self.push_screen(DeepResearchScreen())


def main():
    app = CouncilDemo()
    app.run()


if __name__ == "__main__":
    main()
