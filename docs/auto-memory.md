# Auto memory keeping — the rule

**Rule: keep the project's memory current, without being asked.**

A new chat starts with no knowledge of this project except what's written
down. If the written record is stale, the next session confidently acts on
wrong facts — that has already happened here (a rating given from a stale
read, and gold documented as a futures proxy for a day after we'd switched to
real spot).

## Two different memories — don't confuse them

| | Where | Who sees it | Holds |
|---|---|---|---|
| **Auto-memory** | `~/.claude/projects/.../memory/` | Claude only, loads into every new chat | How Filip works, preferences, project state, hard-won gotchas |
| **Repo docs** | `CLAUDE.md` + `docs/` | Anyone, versioned in git | What the project is, rules, roadmap, decisions, changelog |

Auto-memory is private and automatic. The repo docs are shared and permanent.
They should not duplicate each other: memory holds *how we work*, the docs
hold *what the project is*.

## When to update — no permission needed

Update **as it happens**, in the same session, not "later":

- **A fact changed** → data source, default, ticker, baseline number, file
  moved or deleted. Anything a future session would state confidently and be
  wrong about.
- **Filip corrected me or stated a preference** → record it as a rule, with
  the *why*. If he had to say it twice, it definitely belongs in memory.
- **A decision got made** → what we chose, what we rejected, and the reason.
  The reason is the part that stops it being re-litigated.
- **Something was finished** → mark it done. A roadmap item still listed as
  "next" after it shipped is worse than no roadmap.
- **A trap was discovered** → the kind that costs an hour to rediscover.
  Example: Dukascopy ships calendar-day bars, so a 20-bar MA would silently
  span 20 *calendar* days.

## How to keep it clean

- **Correct in place; don't append.** Rewrite the wrong line. An out-of-date
  memory file is worse than a short one.
- **Delete what's no longer true.** Superseded facts are landmines.
- **State absolutes, not relatives.** "2026-07-19", never "yesterday".
- **Say the why.** "Dukascopy, because Yahoo has no spot gold" survives; a
  bare "use Dukascopy" gets overturned by the next person with an opinion.
- **Don't record what the code already says.** Structure, history and
  filenames are readable from the repo. Record what *isn't* in the code:
  decisions, preferences, and reasons.

## Which file gets what

- `CLAUDE.md` — identity, stack, rules of engagement, links out. Changes rarely.
- `docs/roadmap.md` — what we're building and why. Changes when priorities move.
- `docs/flagged.md` — open decisions, and what to distrust. Changes often.
- `docs/changelog.md` — one short line per change, by day. Append every session.
- Auto-memory — how Filip works, and current project state.

## The end-of-session check

Before finishing, ask: *if the next session read only these files, would it
believe anything untrue?* Fix that before stopping.
