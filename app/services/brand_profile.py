"""Brand profile distillation service (P7-5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from ..db import session_scope
from ..models import Asset, BrainDocument, BrandProfileVersion, FeedbackEvent

_BRAND_LABEL = "BRAND" + " NAME"

BRAND_PROFILE_DISTILLATION_PROMPT = f"""SYSTEM:

You are the brand strategist for {_BRAND_LABEL}, a streetwear label. You distill observed evidence into an operating brand profile that other agents follow when generating content. You work ONLY from the evidence provided — no generic marketing advice, no invented rules.

OUTPUT CONTRACT: respond with ONLY markdown containing exactly these five H2 sections, in this order: `## Voice rules`, `## Banned phrases`, `## Visual codes`, `## Proven hooks`, `## Audience notes`.

HARD CONSTRAINTS:
1. Every bullet must cite the evidence ids it derives from, in parentheses at the end (e.g. `(fb_123, pair_45)`). A bullet with no citation is invalid.
2. Prefer patterns from SELECTED versions and positive feedback; a pattern appearing only in unselected/negative material may ONLY appear under Banned phrases or as a "avoid" rule.
3. Carry forward rules from the current profile unless newer evidence contradicts them; when reversing or removing a rule, add a bullet noting the reversal with the contradicting ids.
4. Banned phrases must actually appear in rejected or negatively-received material — never ban speculatively.
5. Maximum 40 bullets total across all sections; each bullet at most 2 sentences, written as an imperative instruction.
6. If a section has insufficient evidence this period, write exactly: `Insufficient evidence this period.` — never pad with plausible-sounding filler.

USER (template):

CURRENT PROFILE (v{{version_no}}): {{current_profile_md}}
FEEDBACK EVENTS since {{since_date}} (id, target, sentiment, text): {{feedback_events}}
SELECTED vs UNSELECTED version pairs (pair id, selected text/params, unselected text/params): {{version_pairs}}
METRIC INSIGHTS (if any): {{metric_insights}}

Write the new profile markdown now."""

REQUIRED_PROFILE_SECTIONS = (
    "## Voice rules",
    "## Banned phrases",
    "## Visual codes",
    "## Proven hooks",
    "## Audience notes",
)


@dataclass(frozen=True)
class DistillationPrompt:
    prompt: str
    evidence_ids: list[str]
    current_version_no: int
    since_date: str


def build_distillation_prompt() -> DistillationPrompt:
    latest, feedback_events, version_pairs, metric_insights = _collect_evidence()
    current_version_no = latest.version_no if latest else 0
    current_profile_md = latest.profile_md if latest else "No prior profile."
    since_date = latest.created_at.date().isoformat() if latest else (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    evidence_ids = [
        *[str(item["id"]) for item in feedback_events],
        *[str(item["pair_id"]) for item in version_pairs],
        *[str(item["id"]) for item in metric_insights],
    ]
    return DistillationPrompt(
        prompt=BRAND_PROFILE_DISTILLATION_PROMPT.format(
            version_no=current_version_no,
            current_profile_md=current_profile_md,
            since_date=since_date,
            feedback_events=json.dumps(feedback_events, ensure_ascii=False, indent=2),
            version_pairs=json.dumps(version_pairs, ensure_ascii=False, indent=2),
            metric_insights=json.dumps(metric_insights, ensure_ascii=False, indent=2),
        ),
        evidence_ids=evidence_ids,
        current_version_no=current_version_no,
        since_date=since_date,
    )


async def distill_brand_profile() -> dict[str, Any]:
    distillation = build_distillation_prompt()
    profile_md = (await run_distillation_agent(distillation.prompt)).strip()
    valid, reason = validate_profile_markdown(profile_md)
    if not valid:
        return {"created": False, "reason": reason, "evidence_ids": distillation.evidence_ids}

    with session_scope() as session:
        current = session.execute(select(func.max(BrandProfileVersion.version_no))).scalar_one()
        version_no = int(current or 0) + 1
        session.add(
            BrandProfileVersion(
                version_no=version_no,
                profile_md=profile_md,
                distilled_from_json=json.dumps(
                    {
                        "evidence_ids": distillation.evidence_ids,
                        "previous_version_no": distillation.current_version_no,
                        "since_date": distillation.since_date,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    return {"created": True, "version_no": version_no, "evidence_ids": distillation.evidence_ids}


async def run_distillation_agent(prompt: str) -> str:
    from .agents import get_agent, run_agent

    return await run_agent(get_agent("content_strategist"), prompt)


def validate_profile_markdown(profile_md: str) -> tuple[bool, str]:
    positions: list[int] = []
    for section in REQUIRED_PROFILE_SECTIONS:
        position = profile_md.find(section)
        if position < 0:
            return False, f"missing section: {section}"
        positions.append(position)
    if positions != sorted(positions):
        return False, "profile sections out of order"
    return True, ""


def _collect_evidence() -> tuple[BrandProfileVersion | None, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    with session_scope() as session:
        latest = session.execute(
            select(BrandProfileVersion).order_by(BrandProfileVersion.version_no.desc())
        ).scalars().first()
        if latest is not None:
            session.expunge(latest)

        feedback = session.execute(
            select(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(50)
        ).scalars().all()
        feedback_events = [
            {
                "id": event.id,
                "target": event.output_path,
                "sentiment": _sentiment(event.rating),
                "text": " ".join(part for part in [event.comment, event.improvement_request] if part).strip(),
            }
            for event in feedback
        ]

        assets = session.execute(select(Asset).order_by(Asset.id.desc()).limit(50)).scalars().unique().all()
        version_pairs: list[dict[str, Any]] = []
        for asset in assets:
            selected = next((version for version in asset.versions if version.is_selected), None)
            unselected = next((version for version in reversed(asset.versions) if not version.is_selected), None)
            if selected is None or unselected is None:
                continue
            version_pairs.append(
                {
                    "pair_id": f"pair_{asset.id}_{selected.version_no}_{unselected.version_no}",
                    "selected": _version_evidence(selected.content_text, selected.params_json),
                    "unselected": _version_evidence(unselected.content_text, unselected.params_json),
                }
            )
            if len(version_pairs) >= 25:
                break

        metric_rows = session.execute(
            select(BrainDocument).where(BrainDocument.kind == "metric_insight").order_by(BrainDocument.id.desc()).limit(25)
        ).scalars().all()
        metric_insights = [{"id": f"metric_{row.id}", "text": row.text, "meta": row.meta_json} for row in metric_rows]

    return latest, feedback_events, version_pairs, metric_insights


def _version_evidence(content_text: str | None, params_json: str) -> dict[str, str]:
    return {
        "text": (content_text or "")[:2000],
        "params": params_json[:1200],
    }


def _sentiment(rating: int | None) -> str:
    if rating is None:
        return "unknown"
    if rating >= 4:
        return "positive"
    if rating <= 2:
        return "negative"
    return "mixed"
