"""A theme is a protocol, not a topic.

Three of the last five video captions gave the viewer nothing to do ("Minder
presteren, meer voelen"). These gates are what stops an explainer reaching a post.
"""

from __future__ import annotations

from datetime import date

from app.agents.pipeline import (
    _has_dose,
    _is_vague_action,
    _post_action_violations,
    _theme_action_violations,
    _themes_block,
)
from app.agents.schemas import (
    GeneratorOutput,
    PostReferences,
    PostSpec,
    PostTakeaway,
    TrendBrief,
    TrendTheme,
)

WEEK = date(2026, 10, 5)


def _theme(**over: str) -> TrendTheme:
    base = dict(
        title="De wandeling van twee minuten",
        summary="Kort lopen vlak na het eten.",
        why_relevant="Keep Moving / Move naturally",
        action="Loop twee minuten na het eten",
        dose="2 minuten, binnen 30 minuten na elke maaltijd",
        payoff="Je zakt 's middags minder weg",
        evidence="Kort lopen na de maaltijd vlakt de glucosepiek af.",
        source_url="https://example.nl/walk",
    )
    base.update(over)
    return TrendTheme(**base)  # type: ignore[arg-type]


def _post(action: str, dose: str, caption: str) -> PostSpec:
    return PostSpec(
        pillar="Keep Moving",
        type="video",
        scene_prompt="The Blue Fit mascot at the office",
        takeaway=PostTakeaway(action=action, dose=dose, payoff="minder middagdip"),
        caption_template="question",
        caption=caption,
        references_used=PostReferences(value="Move naturally"),
    )


# ---- what counts as an action --------------------------------------------------


def test_the_named_failure_modes_are_rejected() -> None:
    """These exact phrases are what the captions used to end on."""
    for vague in ("Beweeg meer", "eet gezonder", "Luister naar je lichaam",
                  "neem rust", "Wees bewust van je houding", ""):
        assert _is_vague_action(vague), vague


def test_a_countable_action_passes() -> None:
    for real in ("Loop twee minuten na het eten",
                 "Zet je glas water klaar voor je koffie",
                 "Neem de trap naar de derde verdieping"):
        assert not _is_vague_action(real), real


def test_a_dose_needs_an_amount_or_a_moment() -> None:
    assert _has_dose("2 minuten")
    assert _has_dose("binnen 30 minuten na het eten")
    assert _has_dose("elke ochtend")  # no digit, but an unmistakable moment
    assert not _has_dose("regelmatig")
    assert not _has_dose("wanneer het uitkomt")


# ---- the theme gate ------------------------------------------------------------


def test_a_protocol_theme_has_no_violations() -> None:
    assert _theme_action_violations(TrendBrief(week_start=WEEK, themes=[_theme()])) == []


def test_an_explainer_theme_is_flagged_with_its_title() -> None:
    brief = TrendBrief(week_start=WEEK, themes=[_theme(action="Beweeg meer")])
    problems = _theme_action_violations(brief)
    assert len(problems) == 1
    assert "De wandeling van twee minuten" in problems[0]


def test_a_doseless_theme_is_flagged_separately() -> None:
    brief = TrendBrief(week_start=WEEK, themes=[_theme(dose="regelmatig")])
    assert "dose has no amount" in _theme_action_violations(brief)[0]


def test_only_the_bad_themes_are_flagged() -> None:
    brief = TrendBrief(
        week_start=WEEK,
        themes=[_theme(title="Good"), _theme(title="Bad", action="Wees bewust")],
    )
    problems = _theme_action_violations(brief)
    assert len(problems) == 1 and "Bad" in problems[0]


# ---- the post gate -------------------------------------------------------------


def test_a_post_that_states_its_action_passes() -> None:
    out = GeneratorOutput(posts=[
        _post("Loop twee minuten na het eten", "2 minuten",
              "Loop twee minuten na het eten, meer is het niet. Je middag zakt minder ver weg.")
    ])
    assert _post_action_violations(out) == []


def test_a_caption_that_never_names_the_action_is_flagged() -> None:
    """The takeaway existing in the JSON is worth nothing if nobody reads it."""
    out = GeneratorOutput(posts=[
        _post("Loop twee minuten na het eten", "2 minuten",
              "Minder presteren, meer voelen. Hoe zorg jij voor balans?")
    ])
    assert "caption does not state the action" in _post_action_violations(out)[0]


def test_an_action_of_only_short_words_is_not_falsely_flagged() -> None:
    """Short words match any text, so the caption check skips rather than guesses."""
    out = GeneratorOutput(posts=[_post("Ga uit", "1 keer per dag", "Iets heel anders.")])
    assert not any("state the action" in p for p in _post_action_violations(out))


# ---- what the generator is shown -----------------------------------------------


def test_the_themes_block_puts_the_protocol_in_front_of_the_generator() -> None:
    block = _themes_block(TrendBrief(week_start=WEEK, themes=[_theme()]), raw="{}")
    assert "- ACTION: Loop twee minuten na het eten" in block
    assert "- DOSE: 2 minuten, binnen 30 minuten na elke maaltijd" in block
    assert "- PAYOFF: Je zakt 's middags minder weg" in block
    assert "https://example.nl/walk" in block


def test_an_unvalidated_brief_falls_back_to_the_raw_text() -> None:
    """A loose brief still runs the week — it must not arrive empty."""
    assert _themes_block(None, raw="```json\n{\"themes\": []}\n```") == '{"themes": []}'


def test_a_moment_the_live_run_wrongly_rejected_now_passes() -> None:
    """'Direct na het opstaan' says exactly when, and cost a retry before this."""
    assert _has_dose("Direct na het opstaan")
    assert _has_dose("vóór je koffie")
    assert _has_dose("zodra je thuiskomt")


# ---- client copy ---------------------------------------------------------------


def test_em_dashes_never_reach_the_client() -> None:
    """The client asked for them gone; a prompt rule alone cannot guarantee it."""
    from app.agents.schemas import strip_em_dashes

    assert strip_em_dashes("zenuwstelsel—je lichaam") == "zenuwstelsel, je lichaam"
    assert strip_em_dashes("rust pakken — ook een prestatie") == "rust pakken, ook een prestatie"
    assert strip_em_dashes("geen streepjes hier") == "geen streepjes hier"


def test_a_generated_caption_is_cleaned_on_the_way_in() -> None:
    post = _post("Loop twee minuten", "2 minuten",
                 "Loop twee minuten na het eten—je middag wordt beter.")
    assert "—" not in post.caption
    assert "eten, je middag" in post.caption


# ---- no medical claims ---------------------------------------------------------


def test_physiology_is_allowed_but_risk_claims_are_not() -> None:
    """Calibrated on real researcher output: organ words stay legal, claims don't."""
    from app.agents.pipeline import _clinical_claims

    for safe in (
        "Je bloedsuiker piekt minder en je rug voelt minder stijf",
        "verlagen de hartslag, bloeddruk en stresshormonen",
        "Je cortisolniveau daalt en je stemming verbetert",
    ):
        assert _clinical_claims(safe) == [], safe

    for blocked in (
        "Je vermindert het risico op gezondheidsproblemen",
        "een lagere kans op overlijden",
        "een forse daling van het sterfterisico",
        "verlaagt je risico op diabetes type 2",
    ):
        assert _clinical_claims(blocked), blocked


def test_a_clinical_theme_is_sent_back_to_the_researcher() -> None:
    brief = TrendBrief(week_start=WEEK, themes=[
        _theme(payoff="Je vermindert het risico op hart- en vaatziekten")
    ])
    assert "medical claim" in _theme_action_violations(brief)[0]


def test_a_clinical_caption_is_sent_back_to_the_generator() -> None:
    out = GeneratorOutput(posts=[
        _post("Loop twee minuten", "2 minuten",
              "Loop twee minuten na het eten. Dit verlaagt je risico op diabetes.")
    ])
    assert any("medical claim" in p for p in _post_action_violations(out))
