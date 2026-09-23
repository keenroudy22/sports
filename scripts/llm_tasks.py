"""What the local model is asked to do, and nothing else.

Every task builds its prompt from the pick's own fields and the sourced facts the run gathered,
calls scripts/llm.py, and puts the answer through the style check and the numbers guard. A polish
that fails either guard is retried once with the failures listed, then the template stands. A
judgment that comes back malformed is reported as unavailable so the run can hold instead of guess.

  python scripts/llm_tasks.py why PICK_ID        polish a published pick's why and show the guard result
  python scripts/llm_tasks.py judge PICK_ID      weigh today's injury listings against a published pick

Stdlib only.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm

JUDGE_SCHEMA = {'type': 'object',
                'properties': {'argues_against': {'type': 'boolean'},
                               'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                               'fact_ids': {'type': 'array', 'items': {'type': 'string'}},
                               'note': {'type': 'string'}},
                'required': ['argues_against', 'confidence', 'fact_ids', 'note']}

POLISH_USER = """Rewrite the text below in the house style. Keep every fact and every number exactly as written,
keep it about the same length, and do not add anything that is not in the material. Return only the rewritten text.

Material (the pick's own fields):
{material}

Text to rewrite:
{text}"""

RETRY_NOTE = """

Your previous attempt failed these checks: {problems}. Fix them and return only the text."""

JUDGE_SYSTEM = """You weigh sourced facts about a football game against a proposed pick. You never predict, you never
compute, and you never add facts. A fact argues against the pick only if it plausibly changes what the pick depends on:
a listed quarterback for a total, the player's own listing or his quarterback for a player prop, several starters out
on one side, weather for a total. A listing marked Active or a fact about the other team's depth players does not.
When you are not sure, say confidence low and explain in one sentence."""

JUDGE_USER = """Pick:
{pick}

Facts (each has an id):
{facts}

Does any fact argue against this pick? Answer in JSON with argues_against, confidence (high, medium or low), fact_ids
(the ids of the facts you relied on, empty if none) and a one-sentence note in plain words with no numbers."""

X_SYSTEM = llm.STYLE_SYSTEM + """
You also write like the owner of a small sports account: casual, terse, a friend at the kitchen table. Under 240
characters. No hashtags, no emoji, no dashes, no hype. Never add a number that is not in the material."""


def material_for(pick, extra=()):
    fields = {k: v for k, v in pick.items() if not k.startswith('_') and k not in ('why', 'risk', 'sources', 'legs')}
    fields['desk'] = pick.get('_desk') or {}
    lines = [json.dumps(fields, indent=1, ensure_ascii=False, default=str)]
    for item in extra:
        lines.append(json.dumps(item, ensure_ascii=False, default=str))
    return '\n'.join(lines)


def guarded(text, pick, extra=()):
    """The guard problems for a candidate text, style first."""
    problems = llm.check_style(text)
    ok, strays = llm.numbers_ok(text, pick, extra)
    if not ok:
        problems.append(f"numbers not in the material: {', '.join(strays)}")
    return problems


def polish(text, pick, extra=(), system=None, send=None, max_tokens=400):
    """The model's rewrite of a templated text, or the template when the rewrite fails the guards twice.

    Returns (text, note): note says 'polished', or why the template stands.
    """
    if not text:
        return text, 'nothing to polish'
    user = POLISH_USER.format(material=material_for(pick, extra), text=text)
    problems = []
    for attempt in range(2):
        prompt = user + (RETRY_NOTE.format(problems='; '.join(problems)) if problems else '')
        try:
            draft = llm.draft(system or llm.STYLE_SYSTEM, prompt, max_tokens=max_tokens, send=send)
        except llm.LLMUnavailable as error:
            return text, f'model unavailable: {error}'
        problems = guarded(draft, pick, extra)
        if not problems:
            return draft, 'polished'
    return text, f"template kept: {'; '.join(problems)}"


def why_for(pick, facts=(), send=None):
    return polish(pick.get('why') or '', pick, facts, send=send)


def risk_for(pick, facts=(), send=None):
    return polish(pick.get('risk') or '', pick, facts, send=send)


def summary_for(report, send=None):
    """A report's summary, polished against every number the report itself carries."""
    material = {k: v for k, v in report.items() if k != 'summary'}
    return polish(report.get('summary') or '', material, send=send, max_tokens=600)


def x_polish(text, pick, send=None):
    return polish(text, pick, system=X_SYSTEM, send=send, max_tokens=160)


def judge_against(candidate, facts, send=None):
    """{'argues_against', 'confidence', 'fact_ids', 'note'} or None when the model is unavailable or malformed.

    fact_ids that do not exist are dropped; an 'against' with no surviving id is downgraded to low confidence,
    because a judgment that cannot point at its evidence is not one the run acts on.
    """
    shown = {k: v for k, v in candidate.items() if not k.startswith('_') and k not in ('why', 'risk', 'sources')}
    facts_text = '\n'.join(f"- {f.get('id')}: {f.get('claim')} (source: {f.get('source')})" for f in facts) or '- none'
    try:
        verdict = llm.draft_json(JUDGE_SYSTEM, JUDGE_USER.format(pick=json.dumps(shown, ensure_ascii=False, default=str),
                                                                 facts=facts_text), JUDGE_SCHEMA, send=send)
    except llm.LLMUnavailable:
        return None
    if not isinstance(verdict, dict) or not isinstance(verdict.get('argues_against'), bool):
        return None
    known = {f.get('id') for f in facts}
    ids = [i for i in (verdict.get('fact_ids') or []) if i in known]
    confidence = verdict.get('confidence') if verdict.get('confidence') in ('high', 'medium', 'low') else 'low'
    if verdict['argues_against'] and not ids:
        confidence = 'low'
    return {'argues_against': verdict['argues_against'], 'confidence': confidence, 'fact_ids': ids,
            'note': str(verdict.get('note') or '')[:300]}


# ------------------------------------------------------------------ command line

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('task', choices=('why', 'risk', 'judge'))
    parser.add_argument('pick_id')
    args = parser.parse_args(argv)
    import gates
    stores = gates.Stores()
    now = datetime.now(timezone.utc)
    ctx = stores.as_of(now)
    pick = ctx.first.get(args.pick_id)
    if not pick:
        sys.exit(f'{args.pick_id} is not in research/')
    pick = dict(pick)
    pick['_desk'] = gates.desk_for(pick, ctx)
    if not llm.available():
        sys.exit(f'Ollama is not reachable at {llm.base_url()}')
    print(f'model {llm.model_name()} at {llm.base_url()}\n')
    if args.task in ('why', 'risk'):
        before = pick.get(args.task) or ''
        text, note = (why_for if args.task == 'why' else risk_for)(pick)
        print(f'--- template\n{before}\n\n--- model ({note})\n{text}\n')
        problems = guarded(text, pick)
        print('guard:', 'clean' if not problems else '; '.join(problems))
        return 0 if not problems else 1
    import run
    game = ctx.games.get((pick.get('gameIds') or [None])[0])
    if not game:
        sys.exit('the game is no longer in the slate')
    facts = run.evidence(dict(pick, _team=ctx.player_team.get(str(pick.get('athleteId') or ''))), ctx, stores.context_file)
    verdict = judge_against(pick, facts)
    print(f'{len(facts)} facts')
    for fact in facts:
        print(f"  {fact['id']} [{fact['direction']}] {fact['claim']}")
    print('\nverdict:', json.dumps(verdict, indent=1) if verdict else 'unavailable')
    return 0


if __name__ == '__main__':
    sys.exit(main())
