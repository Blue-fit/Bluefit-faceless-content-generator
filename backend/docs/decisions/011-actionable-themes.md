# 011 — A theme is a protocol, not a topic

**Date:** 2026-10-01
**Status:** accepted

## Context

The client reported that the videos were not worth interacting with: they
explained *why* you should move and ended with nothing the viewer could use.
"Good to know", then nothing.

The last five video captions in production bear this out:

| week | takeaway |
|---|---|
| 09-28 | "zet eens een timer om elk uur vijf minuten te staan" — sentence 4 of 5 |
| 09-18 | "lunchwandeling van exact 10 minuten" — sentence 4, payoff "doet al wonderen" |
| 09-11 | none — "Minder presteren, meer voelen." |
| 09-04 | none — "Met wie plan jij binnenkort een rustig moment in?" |
| 08-31 | none — "Met wie deel jij je volgende wandeling?" |

Three of five gave the viewer nothing to do. The two that did buried the action
behind three sentences of philosophy and paid it off with a hand-wave.

The generator prompt already asked for "one concrete piece of advice the viewer
can act on today". It was not enough, and could not be: a `TrendTheme` was
`title`, `summary`, `why_relevant`, `source_url`, and the researcher was asked for
"topics and angles". **Nothing in the contract held a thing the viewer does.** A
single clause in the generator cannot rescue a theme that was never built around
an action.

## Decision

A theme is **one thing a member can do**, not a subject to discuss. `TrendTheme`
and `PostSpec` now carry it as required structure:

- `action` — the one thing the viewer does, imperative, Dutch, concrete
- `dose` — how much, how often, or when: a number or an unmistakable moment
- `payoff` — what they notice from doing it
- `evidence` — one line of what the source actually says (themes only)

The researcher's test for shipping a theme: **could a member do this today,
without buying anything, and know tonight whether they did it?** The vague
register is banned by name in the prompt — *beweeg meer*, *wees bewust*, *neem
rust* — because those are the exact phrases the failing captions ended on.

Three consequences downstream:

1. **The video `beat` is the action being performed.** Bluey does the thing the
   viewer should copy, at its real dose. A beat that illustrates an idea (a steady
   mascot while a jogger blurs past) is beautiful and teaches nothing.
2. **The caption states the action by sentence two**, after at most one sentence
   of payoff-the-hook. A reader who stops there still knows what to do.
3. **The hook is untouched.** It stays pure bait; the caption still holds the
   value. This decision does not reopen that one.

Enforcement mirrors the existing weekly-anchor gate: pure violation functions
(`_theme_action_violations`, `_post_action_violations`) plus one best-effort
re-prompt. The post-level check shares the correction call with the value rules
rather than adding a third paid retry, since the generator rewrites all three
posts either way. Nothing here can block a weekly run: a thin brief still beats no
posts, exactly as a malformed one does.

## Scope and limits

**Payoffs may be physical, never clinical.** "Je bloedsuiker piekt minder" is
allowed; "verlaagt je risico op diabetes type 2" is not. Blue Fit is a wellness
club, not a clinic — it diagnoses nothing and treats nothing. The existing medical
blocklist in `search_demand.py` stays, widened for substance queries that the new
dose-shaped seeds surfaced.

The gate is lexical, not semantic: it catches a named vague verb and a dose with
no number or moment. A grammatically concrete action that is useless in practice
will pass. That is accepted — the prompt does the judgement, the gate catches the
collapse back into the old register.

## Alternatives rejected

- **Only strengthening the generator prompt.** Tried already, in the clause that
  produced the 09-18 and 09-28 captions. It moves the action from absent to
  buried, because the theme still has none.
- **A separate retry for actionability.** A second paid generator call for a
  rewrite that regenerates all three posts anyway.
- **Numbers from studies, quoted as numbers.** More concrete, but a wellness club
  publishing "-30%" invites argument it cannot win and ages badly.
