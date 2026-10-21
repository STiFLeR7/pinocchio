"""Nexus operator onboarding — a staged, bring-the-system-online experience.

Runs a sequence of validation stages (system → configuration → git → sandbox → discord →
smtp → research → scheduler → runtime → memory → operator → finish), styled like an operating
system coming online.

SAFE BY DEFAULT: every check is read-only and performs **no external sends and no network I/O**
(no Discord messages, no emails, no LLM calls). Configuration is reported only as
present / missing / invalid — secret *values* are never printed. Live delivery is a separate,
explicitly gated capability and is intentionally not performed here.

Run:  ``python -m nexus.onboarding``  (or ``python -m nexus onboard``)
"""

from __future__ import annotations

import asyncio
import contextlib
import enum
import os
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from nexus.config import NexusSettings, get_settings

# --------------------------------------------------------------------------- operator identity

#: The primary operator being onboarded. Identity only — NOT a credential store (constraint).
OPERATOR_NAME = "Hill Patel"
OPERATOR_USERNAME = "stifler"
OPERATOR_EMAIL = "hillaniljppatel@gmail.com"

NEXUS_VERSION = "1.1.0"
NEXUS_CODENAME = "Containment"


# --------------------------------------------------------------------------- result model


class Status(enum.StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"


@dataclass
class Check:
    name: str
    status: Status
    detail: str = ""


@dataclass
class Stage:
    title: str
    checks: list[Check] = field(default_factory=list)

    @property
    def status(self) -> Status:
        if any(c.status is Status.FAIL for c in self.checks):
            return Status.FAIL
        if any(c.status is Status.WARN for c in self.checks):
            return Status.WARN
        return Status.OK


# --------------------------------------------------------------------------- styling


class _C:
    """ANSI colors; disabled automatically when stdout is not a TTY."""

    enabled = True

    @classmethod
    def wrap(cls, code: str, s: str) -> str:
        if not cls.enabled:
            return s
        return f"\x1b[{code}m{s}\x1b[0m"


def _c(code: str, s: str) -> str:
    return _C.wrap(code, s)


#: Unicode vs ASCII glyph sets — selected at runtime based on stdout encoding capability.
_GLYPHS_UNICODE = {"ok": "✔", "warn": "▲", "fail": "✘", "info": "•", "h": "─", "dash": "—"}
_GLYPHS_ASCII = {"ok": "+", "warn": "!", "fail": "x", "info": "-", "h": "-", "dash": "-"}
_glyphs = _GLYPHS_ASCII  # safe default; upgraded by _init_output()

_MARK_COLOR = {Status.OK: "32", Status.WARN: "33", Status.FAIL: "31", Status.INFO: "36"}


def _init_output() -> None:
    """Force UTF-8 stdout when possible; choose a glyph set the terminal can actually encode."""
    global _glyphs
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "".join(_GLYPHS_UNICODE.values()).encode(enc)
        _glyphs = _GLYPHS_UNICODE
    except Exception:
        _glyphs = _GLYPHS_ASCII
    _C.enabled = bool(getattr(sys.stdout, "isatty", lambda: False)())


def _mark(status: Status) -> str:
    key = {Status.OK: "ok", Status.WARN: "warn", Status.FAIL: "fail", Status.INFO: "info"}[status]
    return _c(_MARK_COLOR[status], _glyphs[key])


def _print_banner() -> None:
    line = _glyphs["h"] * 58
    print(_c("36", f"+{line}+"))
    title = "  NEXUS - AI Orchestration Control Plane".ljust(58)
    sub = f"  v{NEXUS_VERSION} \"{NEXUS_CODENAME}\"  ·  operator onboarding".ljust(58)
    print(_c("36", "|") + _c("1;37", title) + _c("36", "|"))
    print(_c("36", "|") + _c("90", sub) + _c("36", "|"))
    print(_c("36", f"+{line}+"))
    print(_c("90", "  safe mode · read-only checks · no external sends\n"))


def _print_stage(index: int, total: int, stage: Stage) -> None:
    header = f"[{index}/{total}] {stage.title}"
    print(_c("1;37", header) + "  " + _mark(stage.status))
    for c in stage.checks:
        detail = f"  {_glyphs['dash']} {c.detail}" if c.detail else ""
        print(f"    {_mark(c.status)} {c.name}{_c('90', detail)}")
    print()


# --------------------------------------------------------------------------- stages (read-only)


def stage_system() -> Stage:
    import platform
    import sys

    st = Stage("System checks")
    py = sys.version_info
    py_ok = (py.major, py.minor) >= (3, 12)
    st.checks.append(
        Check(
            "Python runtime",
            Status.OK if py_ok else Status.FAIL,
            f"{py.major}.{py.minor}.{py.micro} ({'>=3.12' if py_ok else 'requires 3.12+'})",
        )
    )
    st.checks.append(Check("Platform", Status.INFO, platform.platform()))
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    st.checks.append(
        Check(
            "Virtual environment",
            Status.OK if in_venv else Status.WARN,
            "active" if in_venv else "not detected (system interpreter)",
        )
    )
    for d in ("data", "config"):
        st.checks.append(
            Check(
                f"Directory '{d}/'",
                Status.OK if os.path.isdir(d) else Status.WARN,
                "present" if os.path.isdir(d) else "missing (created on first run)",
            )
        )
    return st


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    if isinstance(value, int):
        return value != 0
    return bool(value)


def stage_configuration(settings: NexusSettings) -> Stage:
    """Report required config as present / missing / invalid. Never prints secret values."""
    st = Stage("Configuration validation")

    def req(name: str, ok: bool, present_msg: str, missing_msg: str) -> None:
        st.checks.append(
            Check(name, Status.OK if ok else Status.FAIL, present_msg if ok else missing_msg)
        )

    def opt(name: str, ok: bool, present_msg: str, missing_msg: str) -> None:
        st.checks.append(
            Check(name, Status.OK if ok else Status.WARN, present_msg if ok else missing_msg)
        )

    req(
        "Discord bot token",
        _present(settings.discord.token),
        "present",
        "missing (DISCORD_BOT_TOKEN)",
    )
    req(
        "Discord guild id",
        _present(settings.discord.guild_id),
        "present",
        "missing (DISCORD_GUILD_ID)",
    )
    # A-001: owner ids gate approval authorization — fail-closed if empty.
    owners_ok = _present(settings.discord.owner_ids)
    req(
        "Owner ids (A-001 approval auth)",
        owners_ok,
        f"{len(settings.discord.owner_ids)} configured",
        "MISSING — startup fails closed (set DISCORD_OWNERS)",
    )
    # LLM gateway: research uses OpenRouter; the Nexus agent also accepts GEMINI_API_KEY.
    llm_ok = _present(settings.openrouter.api_key) or _present(os.getenv("GEMINI_API_KEY"))
    req(
        "LLM gateway key",
        llm_ok,
        "present",
        "missing (OPENROUTER_API_KEY or GEMINI_API_KEY)",
    )
    # Email (SMTP) — code reads NEXUS_EMAIL__* fields.
    email = settings.email
    smtp_ok = _present(email.smtp_host) and _present(email.from_address)
    opt(
        "SMTP email config",
        smtp_ok and _present(email.username) and _present(email.password),
        "host/from/credentials present",
        "incomplete (NEXUS_EMAIL__USERNAME/PASSWORD/SMTP_HOST/FROM_ADDRESS)",
    )
    return st


def stage_git() -> Stage:
    st = Stage("Git validation")
    git = shutil.which("git")
    st.checks.append(
        Check("git executable", Status.OK if git else Status.FAIL, git or "not found on PATH")
    )
    st.checks.append(
        Check(
            "workspace repository",
            Status.OK if os.path.isdir(".git") else Status.WARN,
            "git repository present" if os.path.isdir(".git") else "no .git in CWD",
        )
    )
    return st


def stage_sandbox(settings: NexusSettings) -> Stage:
    st = Stage("Sandbox validation")
    sb = settings.sandbox
    # Default-secure (Track S): execution requires explicit enablement.
    st.checks.append(
        Check(
            "containment posture",
            Status.OK,
            f"enabled={sb.enabled} provider={sb.provider} network={sb.network_policy} "
            f"fs={sb.filesystem_policy}",
        )
    )
    if sb.provider == "docker":
        docker = shutil.which("docker")
        st.checks.append(
            Check(
                "docker runtime",
                Status.OK if docker else Status.WARN,
                "available" if docker else "provider=docker but docker not on PATH",
            )
        )
    else:
        st.checks.append(
            Check(
                "fallback behavior",
                Status.OK if not sb.enabled else Status.WARN,
                "disabled → execution fail-closed (default-secure)"
                if not sb.enabled
                else f"enabled with local provider '{sb.provider}'",
            )
        )
    return st


def stage_discord(settings: NexusSettings) -> Stage:
    st = Stage("Discord validation")
    d = settings.discord
    st.checks.append(
        Check(
            "bot credentials",
            Status.OK if _present(d.token) and _present(d.guild_id) else Status.FAIL,
            "token + guild present" if _present(d.token) else "missing token/guild",
        )
    )
    st.checks.append(
        Check("channel routing", Status.OK, f"{len(d.channels.model_dump())} channels mapped")
    )
    st.checks.append(
        Check("live delivery", Status.INFO, "deferred — safe mode (no message sent)")
    )
    return st


def stage_smtp(settings: NexusSettings) -> Stage:
    st = Stage("SMTP validation")
    e = settings.email
    complete = all(_present(v) for v in (e.smtp_host, e.smtp_port, e.from_address, e.username, e.password))
    st.checks.append(
        Check(
            "transport config",
            Status.OK if complete else Status.WARN,
            f"host={'set' if _present(e.smtp_host) else 'missing'} "
            f"from={'set' if _present(e.from_address) else 'missing'} "
            f"auth={'set' if _present(e.username) and _present(e.password) else 'missing'}",
        )
    )
    st.checks.append(Check("live delivery", Status.INFO, "deferred — safe mode (no email sent)"))
    return st


def stage_research(settings: NexusSettings) -> Stage:
    st = Stage("Research validation")
    feeds = settings.scheduling.research_feeds
    st.checks.append(
        Check(
            "RSS feeds",
            Status.OK if _present(feeds) else Status.WARN,
            f"{len(feeds)} configured" if _present(feeds) else "none configured",
        )
    )
    st.checks.append(
        Check(
            "OpenRouter gateway",
            Status.OK if _present(settings.openrouter.api_key) else Status.WARN,
            "key present" if _present(settings.openrouter.api_key) else "no OPENROUTER_API_KEY",
        )
    )
    st.checks.append(Check("live run", Status.INFO, "deferred — safe mode (no LLM call)"))
    return st


def stage_scheduler(settings: NexusSettings, session_factory: Any) -> Stage:
    st = Stage("Scheduler validation")
    try:
        from nexus.scheduling.scheduler import build_scheduler

        scheduler = build_scheduler(
            settings,
            session_factory,
            openrouter_client=None,
            discord_service=None,
            email_service=None,
            owner_ids=settings.discord.owner_ids,
            event_gateway=None,
        )
        if scheduler is None:
            st.checks.append(Check("scheduler", Status.WARN, "globally disabled"))
        else:
            job_ids = scheduler.job_ids
            st.checks.append(
                Check("job registration", Status.OK, f"{len(job_ids)} jobs: {', '.join(job_ids)}")
            )
            st.checks.append(Check("autostart", Status.INFO, "not started — safe mode"))
    except Exception as exc:
        st.checks.append(Check("scheduler", Status.FAIL, f"build error: {exc}"))
    return st


def stage_runtime(settings: NexusSettings) -> Stage:
    st = Stage("Runtime validation")
    try:
        from nexus.execution.runners import runtime_registry

        # Registration is import-triggered — import every adapter module first (as the
        # registry resolver does) so all runtimes are registered before we resolve them.
        from nexus.execution.runners.claude import ClaudeRuntimeAdapter  # noqa: F401
        from nexus.execution.runners.gemini import GeminiRuntimeAdapter  # noqa: F401
        from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter  # noqa: F401

        for rid in ("nexus", "gemini", "claude"):
            try:
                cls = runtime_registry.get_adapter_cls(rid)
                st.checks.append(Check(f"runtime '{rid}'", Status.OK, f"resolves -> {cls.__name__}"))
            except Exception as exc:
                st.checks.append(Check(f"runtime '{rid}'", Status.FAIL, str(exc)))
        # Back-compat alias.
        alias = runtime_registry.get_adapter_cls("hermes")
        st.checks.append(
            Check("legacy alias 'hermes'", Status.OK, f"resolves -> {alias.__name__} (back-compat)")
        )
        st.checks.append(Check("live execution", Status.INFO, "deferred — safe mode (no run)"))
    except Exception as exc:
        st.checks.append(Check("runtime registry", Status.FAIL, str(exc)))
    return st


async def stage_memory(settings: NexusSettings, session_factory: Any) -> Stage:
    st = Stage("Memory validation")
    try:
        from nexus.database import get_session

        async with get_session(session_factory) as session:
            await session.execute(text("SELECT 1"))

            def _tables(sync_conn: Any) -> int:
                return len(sa_inspect(sync_conn).get_table_names())

            conn = await session.connection()
            table_count = await conn.run_sync(_tables)
        st.checks.append(Check("database connectivity", Status.OK, "SELECT 1 ok"))
        st.checks.append(Check("schema", Status.OK, f"{table_count} tables present"))
    except Exception as exc:
        st.checks.append(Check("database", Status.FAIL, f"unreachable: {exc}"))
    return st


def stage_operator() -> Stage:
    st = Stage("Operator profile")
    st.checks.append(Check("name", Status.OK, OPERATOR_NAME))
    st.checks.append(Check("username", Status.OK, OPERATOR_USERNAME))
    st.checks.append(Check("email", Status.OK, OPERATOR_EMAIL))
    st.checks.append(
        Check("identity store", Status.INFO, "in-session only — .env remains the source of truth")
    )
    return st


# --------------------------------------------------------------------------- orchestration


async def collect_stages(settings: NexusSettings) -> list[Stage]:
    """Run every read-only stage and return the results (no printing)."""
    from nexus.database import async_session_factory, create_engine

    engine = create_engine(settings.database.url, echo=False)
    session_factory = async_session_factory(engine)
    try:
        stages = [
            stage_system(),
            stage_configuration(settings),
            stage_git(),
            stage_sandbox(settings),
            stage_discord(settings),
            stage_smtp(settings),
            stage_research(settings),
            stage_scheduler(settings, session_factory),
            stage_runtime(settings),
            await stage_memory(settings, session_factory),
            stage_operator(),
        ]
    finally:
        await engine.dispose()
    return stages


def summarize(stages: list[Stage]) -> dict[str, int]:
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for stage in stages:
        s = stage.status
        if s is Status.FAIL:
            counts["fail"] += 1
        elif s is Status.WARN:
            counts["warn"] += 1
        else:
            counts["ok"] += 1
    return counts


async def run_onboarding() -> int:
    """Render the onboarding flow. Returns a process exit code (0 unless a stage FAILED)."""
    _init_output()
    settings = get_settings()
    _print_banner()

    stages = await collect_stages(settings)
    total = len(stages)
    for i, stage in enumerate(stages, start=1):
        _print_stage(i, total, stage)

    counts = summarize(stages)
    line = _glyphs["h"] * 58
    print(_c("90", line))
    verdict = (
        _c("32", "SYSTEM ONLINE")
        if counts["fail"] == 0
        else _c("31", "BLOCKED — remediation required")
    )
    print(
        f"  {verdict}   "
        f"{_c('32', str(counts['ok']) + ' ok')}  "
        f"{_c('33', str(counts['warn']) + ' warn')}  "
        f"{_c('31', str(counts['fail']) + ' fail')}"
    )
    print(_c("90", "  See integration-status-report.md for remediation steps.\n"))
    return 0 if counts["fail"] == 0 else 1


def main() -> None:
    raise SystemExit(asyncio.run(run_onboarding()))


if __name__ == "__main__":
    main()
