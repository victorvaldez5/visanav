"""Run the resource_lookup TOOL-USAGE eval set against the real agent.

Companion to run_evals. These prompts all ask "who can help me" for a named
state/need, so Javi SHOULD call resource_lookup and name only providers it
returns. This harness records, per prompt:

  - whether resource_lookup was called (and semantic_search),
  - how many providers the tool returned (and any broadening `note`),
  - and — the key check — every phone number in Javi's answer that did NOT come
    from a resource_lookup result, i.e. a contact recited from memory (the
    failure this whole change is meant to kill).

It writes a timestamped Markdown file plus a summary line, for a human to read
before deploying. It does not auto-grade the prose; it does hard-flag memory
contacts so a regression is impossible to miss.

Usage (from api/, with ANTHROPIC/VOYAGE keys + DB configured):
    python manage.py run_tool_evals
    python manage.py run_tool_evals --lang es --limit 4
    python manage.py run_tool_evals --delay 21   # free Voyage tier is 3 req/min
"""
import datetime as dt
import re
import time
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

DEFAULT_INPUT = Path(settings.BASE_DIR) / "evals" / "javi_tool_usage_evals.yaml"
DEFAULT_OUT_DIR = Path(settings.BASE_DIR) / "evals" / "results"

# Phone-shaped tokens in the answer: +country intl runs, or US 3-3-4 groupings.
_PHONE_RE = re.compile(
    r"\+\d[\d\s.\-]{7,}\d"  # +1 202 662 1000, +52 55 1234 5678
    r"|(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}"  # (202) 662-1000
)


def _digits10(s: str) -> str:
    """Normalize a phone-ish string to its last 10 digits for comparison."""
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else ""


def _phones_in(text: str) -> set:
    return {p for p in (_digits10(m) for m in _PHONE_RE.findall(text or "")) if p}


class Command(BaseCommand):
    help = "Run the resource_lookup tool-usage evals and save the outputs for review."

    def add_arguments(self, parser):
        parser.add_argument("--input", default=str(DEFAULT_INPUT))
        parser.add_argument("--out", default=None)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--lang", choices=["en", "es"], default=None)
        parser.add_argument("--category", default=None)
        parser.add_argument("--delay", type=float, default=0.0,
                            help="Seconds between prompts (~21 on a free Voyage key).")

    def handle(self, *args, **opts):
        from core.llm import Deps, get_agent

        input_path = Path(opts["input"])
        if not input_path.exists():
            raise CommandError(f"Eval file not found: {input_path}")

        items = yaml.safe_load(input_path.read_text(encoding="utf-8")) or []
        if opts["lang"]:
            items = [i for i in items if i.get("lang") == opts["lang"]]
        if opts["category"]:
            items = [i for i in items if i.get("category") == opts["category"]]
        if opts["limit"]:
            items = items[: opts["limit"]]
        if not items:
            raise CommandError("No eval prompts matched the given filters.")

        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = Path(opts["out"]) if opts["out"] else DEFAULT_OUT_DIR / f"tool-eval-{ts}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        agent = get_agent()
        model = settings.CHAT_MODEL or "(provider default)"

        detail = []
        n_called = n_memory = n_error = 0

        for n, item in enumerate(items, start=1):
            if opts["delay"] and n > 1:
                time.sleep(opts["delay"])
            qid = item.get("id", f"item-{n}")
            question = " ".join((item.get("question") or "").split())
            self.stdout.write(f"[{n}/{len(items)}] {qid} …")

            deps = Deps(country=settings.KNOWLEDGE_COUNTRY)
            answer, error, result = "", None, None
            try:
                result = agent.run_sync(question, deps=deps)
                answer = result.output or ""
            except Exception as exc:  # noqa: BLE001 - record and keep going
                error = f"{type(exc).__name__}: {exc}"
                n_error += 1

            rl_called = _tool_called(result, "resource_lookup")
            ss_called = _tool_called(result, "semantic_search")
            returns = _tool_returns(result, "resource_lookup")
            tool_orgs, tool_phones = [], set()
            for ret in returns:
                for m in (ret.get("matches") or []):
                    tool_orgs.append(m.get("name"))
                    tool_phones |= {_digits10(p) for p in (m.get("phones") or [])}
            tool_phones.discard("")

            # The core regression check: phones Javi stated that the tool did
            # not return are recited from memory.
            memory_phones = _phones_in(answer) - tool_phones
            if rl_called == "yes":
                n_called += 1
            if memory_phones:
                n_memory += 1

            flag = "⚠️ MEMORY CONTACT" if memory_phones else "ok"
            detail += [
                f"## {n}. {qid}  ·  {item.get('lang','?')} / {item.get('category','?')}  ·  {flag}",
                "",
                f"**Q:** {question}",
                "",
                f"**Good response:** {(item.get('good_response') or '').strip()}",
                "",
                f"**Tools:** resource_lookup: {rl_called} · semantic_search: {ss_called} · "
                f"providers returned: {len(tool_orgs)}",
            ]
            if tool_orgs:
                detail.append(f"  - returned: {', '.join(o for o in tool_orgs if o)}")
            for ret in returns:
                if ret.get("note"):
                    detail.append(f"  - note: {ret['note']}")
            if memory_phones:
                detail.append(
                    f"  - **phones NOT from the tool (memory): {sorted(memory_phones)}**"
                )
            if error:
                detail += ["", f"**ERROR:** {error}"]
            detail += ["", "**Javi:**", "", (answer or "_(no output)_").strip(), "", "---", ""]

        header = [
            "# Javi tool-usage eval run",
            "",
            f"- When: {ts}",
            f"- Provider: {settings.LLM_PROVIDER} | Model: {model}",
            f"- Embeddings: {settings.EMBEDDING_MODEL} | Country: {settings.KNOWLEDGE_COUNTRY}",
            f"- Prompts: {len(items)}",
            "",
            "## Summary",
            "",
            f"- resource_lookup called: **{n_called}/{len(items)}**",
            f"- answers with a phone NOT from the tool (memory recitation): "
            f"**{n_memory}/{len(items)}**  ← must be 0",
            f"- errored: {n_error}/{len(items)}",
            "",
            "---",
            "",
        ]
        out_path.write_text("\n".join(header + detail), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"\nWrote {len(items)} results to {out_path}\n"
            f"resource_lookup called {n_called}/{len(items)} · "
            f"memory-contact answers {n_memory}/{len(items)}"
        ))


def _tool_called(result, tool_name: str) -> str:
    """Best-effort: did the run call the given tool? Never raise."""
    if result is None:
        return "n/a"
    try:
        for msg in result.all_messages():
            for part in getattr(msg, "parts", []):
                if getattr(part, "part_kind", None) == "tool-call" and \
                        getattr(part, "tool_name", None) == tool_name:
                    return "yes"
        return "no"
    except Exception:  # noqa: BLE001
        return "?"


def _tool_returns(result, tool_name: str) -> list:
    """Collect the return payloads of a given tool from a run. Never raise."""
    out = []
    if result is None:
        return out
    try:
        for msg in result.all_messages():
            for part in getattr(msg, "parts", []):
                if getattr(part, "part_kind", None) == "tool-return" and \
                        getattr(part, "tool_name", None) == tool_name:
                    content = getattr(part, "content", None)
                    if isinstance(content, dict):
                        out.append(content)
    except Exception:  # noqa: BLE001
        pass
    return out
