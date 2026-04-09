"""Colored terminal output for council with timestamps."""

from datetime import datetime

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BG_GREEN = "\033[42m"
BG_RED = "\033[41m"
BG_BLUE = "\033[44m"


def ts() -> str:
    """Current timestamp for display."""
    return f"{DIM}{datetime.now().strftime('%H:%M:%S.%f')[:-3]}{RESET}"


def header(round_num: int, best: str) -> str:
    return (
        f"\n{BOLD}{CYAN}{'=' * 60}{RESET}\n"
        f"  {ts()} {BOLD}{WHITE}COUNCIL ROUND {round_num}{RESET}  |  Best: {BOLD}{GREEN}{best}{RESET}\n"
        f"{BOLD}{CYAN}{'=' * 60}{RESET}"
    )


def phase(name: str, detail: str = "") -> str:
    return f"\n{ts()} {BOLD}{MAGENTA}{name}{RESET}  {DIM}{detail}{RESET}"


def model_ok(name: str, detail: str, elapsed: float) -> str:
    return f"  {ts()} {GREEN}✓{RESET} {BOLD}{name:20s}{RESET} {detail} {DIM}({elapsed:.1f}s){RESET}"


def model_fail(name: str, reason: str) -> str:
    return f"  {ts()} {RED}✗{RESET} {BOLD}{name:20s}{RESET} {RED}{reason}{RESET}"


def proposal(num: int, title: str, description: str, impact: str) -> str:
    color = GREEN if impact == "large" else YELLOW if impact == "medium" else DIM
    return (
        f"  {ts()} {BOLD}{BLUE}#{num}{RESET} {BOLD}{title}{RESET}\n"
        f"           {DIM}{description[:120]}{RESET}\n"
        f"           Impact: {color}{impact}{RESET}"
    )


def critique(num: int, proposal_id: int, strengths: str, weaknesses: str) -> str:
    return (
        f"  {ts()} {DIM}Critique on #{proposal_id}:{RESET}\n"
        f"           {GREEN}+{RESET} {strengths[:100]}\n"
        f"           {RED}-{RESET} {weaknesses[:100]}"
    )


def vote_result(rank: int, title: str, score: int, max_score: int) -> str:
    pct = score / max_score * 100 if max_score > 0 else 0
    bar_len = int(pct / 5)
    bar = f"{'█' * bar_len}{'░' * (20 - bar_len)}"
    color = GREEN if rank == 1 else YELLOW if rank <= 3 else DIM
    return f"  {ts()} {color}#{rank}{RESET}  {bar}  {BOLD}{score}/{max_score}{RESET}  {title}"


def score_line(score: float, is_best: bool) -> str:
    if is_best:
        return f"  {ts()} Score: {BOLD}{GREEN}{score:.2f}{RESET} {BG_GREEN}{WHITE} NEW BEST {RESET}"
    return f"  {ts()} Score: {BOLD}{YELLOW}{score:.2f}{RESET}"


def record(branch: str, proposer: str) -> str:
    return (
        f"\n{ts()} {BOLD}{CYAN}RECORD{RESET} → {BOLD}exp/{branch}{RESET}\n"
        f"           Proposed by: {BOLD}{proposer}{RESET}"
    )


def implement_start(title: str) -> str:
    return f"\n{ts()} {BOLD}{CYAN}IMPLEMENT{RESET}  Claude Code working on: {BOLD}\"{title}\"{RESET}"


def context_info(
    context_len: int,
    best_score: float | None,
    best_branch: str | None,
    num_experiments: int,
    num_ref_files: int,
    target_file: str,
) -> str:
    lines = [
        f"\n{ts()} {BOLD}{CYAN}CONTEXT{RESET}  Loading challenge state",
        f"           Target: {BOLD}{target_file}{RESET}",
        f"           Reference files: {num_ref_files}",
        f"           Past experiments: {BOLD}{num_experiments}{RESET}",
    ]
    if best_branch:
        lines.append(f"           Best so far: {BOLD}{GREEN}{best_score:.2f}{RESET} ({best_branch})")
    else:
        lines.append(f"           Best so far: {DIM}none (baseline){RESET}")
    lines.append(f"           Context size: {context_len:,} chars")
    return "\n".join(lines)


def prompt_preview(phase_name: str, prompt: str, max_lines: int = 15) -> str:
    """Show a preview of the prompt being sent to models."""
    lines = prompt.split("\n")
    # Show the EXPERIMENT HISTORY section and YOUR TASK section
    preview_lines = []
    in_section = False
    section_count = 0
    for line in lines:
        if line.startswith("# EXPERIMENT HISTORY"):
            in_section = True
            preview_lines.append(f"  {BOLD}{YELLOW}─── Experiment History ───{RESET}")
            continue
        if line.startswith("# YOUR TASK") or line.startswith("# PROPOSALS") or line.startswith("# ALL PROPOSALS"):
            in_section = True
            preview_lines.append(f"  {BOLD}{YELLOW}─── {line.lstrip('# ')} ───{RESET}")
            continue
        if line.startswith("# ") and in_section:
            in_section = False
        if in_section:
            stripped = line.strip()
            if stripped:
                if stripped.startswith("=== exp/"):
                    # Branch header
                    preview_lines.append(f"  {CYAN}{stripped}{RESET}")
                elif stripped.startswith("=="):
                    preview_lines.append(f"  {DIM}{stripped[:100]}{RESET}")
                elif stripped.startswith("## Proposal"):
                    preview_lines.append(f"  {BLUE}{stripped}{RESET}")
                else:
                    preview_lines.append(f"  {DIM}{stripped[:100]}{RESET}")
                section_count += 1
                if section_count > max_lines:
                    preview_lines.append(f"  {DIM}... ({len(lines) - section_count} more lines){RESET}")
                    break

    if not preview_lines:
        preview_lines.append(f"  {DIM}(prompt: {len(prompt):,} chars){RESET}")

    header = f"{ts()} {BOLD}{MAGENTA}PROMPT → {phase_name}{RESET}  {DIM}({len(prompt):,} chars){RESET}"
    return header + "\n" + "\n".join(preview_lines)
