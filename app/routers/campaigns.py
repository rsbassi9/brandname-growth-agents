"""Campaigns CRUD (P1-5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, Campaign
from ..schemas import AssetOut, CampaignIn, CampaignOut

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(session: Session = Depends(get_session)) -> list[Campaign]:
    return session.execute(select(Campaign).order_by(Campaign.created_at.desc())).scalars().all()


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignIn, session: Session = Depends(get_session)) -> Campaign:
    campaign = Campaign(name=payload.name, goal=payload.goal, status=payload.status)
    session.add(campaign)
    session.commit()
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, session: Session = Depends(get_session)) -> Campaign:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}/assets", response_model=list[AssetOut])
def campaign_assets(campaign_id: int, session: Session = Depends(get_session)) -> list[Asset]:
    if session.get(Campaign, campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return session.execute(
        select(Asset).where(Asset.campaign_id == campaign_id).order_by(Asset.created_at.desc())
    ).scalars().all()
