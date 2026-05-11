from __future__ import annotations

import uuid
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.dependencies.auth import get_workspace_member
from app.models import AvailabilityRule, User, Workspace
from app.schemas.scheduling import AvailabilityResponse, AvailabilitySetRequest, AvailabilitySettingsInput, WeeklyAvailabilityRuleInput


class AvailabilityService:
    def get_availability(
        self,
        db: Session,
        current_user: User,
        *,
        workspace_id: uuid.UUID,
        meeting_type_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AvailabilityResponse:
        get_workspace_member(workspace_id, current_user, db)
        rules = self._load_rules(db, workspace_id=workspace_id, meeting_type_id=meeting_type_id, user_id=user_id)
        return self._build_response(workspace_id, meeting_type_id, user_id, rules)

    def set_availability(self, db: Session, current_user: User, payload: AvailabilitySetRequest) -> AvailabilityResponse:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        ZoneInfo(payload.settings.timezone)
        self._delete_scope_rules(db, workspace_id=payload.workspace_id, meeting_type_id=payload.meeting_type_id, user_id=payload.user_id)
        scope = "meeting_type" if payload.meeting_type_id else "user" if payload.user_id else "workspace"
        settings_row = AvailabilityRule(
            workspace_id=payload.workspace_id,
            meeting_type_id=payload.meeting_type_id,
            user_id=payload.user_id,
            scope=scope,
            rule_type="settings",
            timezone=payload.settings.timezone,
            settings_json=payload.settings.model_dump(mode="json"),
            is_enabled=True,
        )
        db.add(settings_row)
        for item in payload.rules:
            db.add(
                AvailabilityRule(
                    workspace_id=payload.workspace_id,
                    meeting_type_id=payload.meeting_type_id,
                    user_id=payload.user_id,
                    scope=scope,
                    rule_type="weekly",
                    weekday=item.weekday,
                    start_minute=self._to_minutes(item.start_time),
                    end_minute=self._to_minutes(item.end_time),
                    timezone=payload.settings.timezone,
                    is_enabled=item.is_enabled,
                )
            )
        db.commit()
        rules = self._load_rules(db, workspace_id=payload.workspace_id, meeting_type_id=payload.meeting_type_id, user_id=payload.user_id)
        return self._build_response(payload.workspace_id, payload.meeting_type_id, payload.user_id, rules)

    def get_runtime_config(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        meeting_type_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AvailabilityResponse:
        rules = self._load_rules(db, workspace_id=workspace_id, meeting_type_id=meeting_type_id, user_id=user_id)
        if not rules and (meeting_type_id or user_id):
            rules = self._load_rules(db, workspace_id=workspace_id, meeting_type_id=None, user_id=None)
        if not rules:
            workspace = db.get(Workspace, workspace_id)
            return AvailabilityResponse(
                workspace_id=workspace_id,
                meeting_type_id=meeting_type_id,
                user_id=user_id,
                rules=[
                    WeeklyAvailabilityRuleInput(weekday=0, start_time="09:00", end_time="17:00"),
                    WeeklyAvailabilityRuleInput(weekday=1, start_time="09:00", end_time="17:00"),
                    WeeklyAvailabilityRuleInput(weekday=2, start_time="09:00", end_time="17:00"),
                    WeeklyAvailabilityRuleInput(weekday=3, start_time="09:00", end_time="17:00"),
                    WeeklyAvailabilityRuleInput(weekday=4, start_time="09:00", end_time="17:00"),
                ],
                settings=AvailabilitySettingsInput(timezone="UTC", fallback_owner_user_id=workspace.owner_user_id if workspace else None),
            )
        return self._build_response(workspace_id, meeting_type_id, user_id, rules)

    def _load_rules(self, db: Session, *, workspace_id: uuid.UUID, meeting_type_id: uuid.UUID | None, user_id: uuid.UUID | None) -> list[AvailabilityRule]:
        query = select(AvailabilityRule).where(AvailabilityRule.workspace_id == workspace_id)
        if meeting_type_id is None:
            query = query.where(AvailabilityRule.meeting_type_id.is_(None))
        else:
            query = query.where(AvailabilityRule.meeting_type_id == meeting_type_id)
        if user_id is None:
            query = query.where(AvailabilityRule.user_id.is_(None))
        else:
            query = query.where(AvailabilityRule.user_id == user_id)
        return db.scalars(query.order_by(AvailabilityRule.rule_type.asc(), AvailabilityRule.weekday.asc().nullsfirst())).all()

    def _delete_scope_rules(self, db: Session, *, workspace_id: uuid.UUID, meeting_type_id: uuid.UUID | None, user_id: uuid.UUID | None) -> None:
        query = delete(AvailabilityRule).where(AvailabilityRule.workspace_id == workspace_id)
        query = query.where(AvailabilityRule.meeting_type_id == meeting_type_id) if meeting_type_id else query.where(AvailabilityRule.meeting_type_id.is_(None))
        query = query.where(AvailabilityRule.user_id == user_id) if user_id else query.where(AvailabilityRule.user_id.is_(None))
        db.execute(query)

    def _build_response(
        self,
        workspace_id: uuid.UUID,
        meeting_type_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        rules: list[AvailabilityRule],
    ) -> AvailabilityResponse:
        settings_row = next((rule for rule in rules if rule.rule_type == "settings"), None)
        settings_payload = settings_row.settings_json if settings_row and settings_row.settings_json else {"timezone": "UTC"}
        weekly_rules = [
            WeeklyAvailabilityRuleInput(
                weekday=int(rule.weekday or 0),
                start_time=self._from_minutes(int(rule.start_minute or 0)),
                end_time=self._from_minutes(int(rule.end_minute or 0)),
                is_enabled=rule.is_enabled,
            )
            for rule in rules
            if rule.rule_type == "weekly"
        ]
        return AvailabilityResponse(
            workspace_id=workspace_id,
            meeting_type_id=meeting_type_id,
            user_id=user_id,
            rules=weekly_rules,
            settings=AvailabilitySettingsInput(**settings_payload),
        )

    def _to_minutes(self, value: str) -> int:
        hours, minutes = value.split(":")
        return int(hours) * 60 + int(minutes)

    def _from_minutes(self, value: int) -> str:
        hours = value // 60
        minutes = value % 60
        return f"{hours:02d}:{minutes:02d}"
