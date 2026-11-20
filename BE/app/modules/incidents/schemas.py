from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.alarms.schemas import AlarmRecord

IncidentStatus = Literal["upcoming", "ongoing", "closed"]


class IncidentSummary(BaseModel):
    incident_id: str
    plant_id: str
    equipment_group_id: str
    equipment_id: str
    equipment_name: str
    status: IncidentStatus = Field(description="as_of 기준 상태: 시작 전, 진행 중, 종료")
    incident_start_time: datetime
    detect_time: datetime
    first_alarm_time: datetime | None
    incident_end_time: datetime | None
    peak_level: int = Field(description="구간 중 도달한 최고 등급 0~4")
    lead_sensor_id: str | None
    lead_sensor_name: str | None
    diagnosis: str = Field(description="분석기 진단(추정)")
    top_risk_fault: str
    top_cof: float
    top_pof: float
    incident_score: float = Field(description="사건 점수. 알람 CoF와 척도가 다르다.")
    alarm_grade: str
    grade_reason: str
    response_time_h: float
    actionable: bool
    alarm_count: int = Field(description="분석기 원본 알람 수")
    linked_alarm_count: int = Field(description="DB에서 사건에 연결된 알람 수")
    trend_count: int


class IncidentList(BaseModel):
    as_of: datetime
    items: list[IncidentSummary]
    next_cursor: str | None


class IncidentCandidate(BaseModel):
    rank: int
    error_type_id: str
    fault: str
    rule_score_s: float
    s_top3_sum: float
    p: float
    speed: int
    impact: int
    w: int
    cof: float
    p_trend: float
    pf_hours: float
    p_pf: float
    pof: float
    score: float
    is_diagnosis: bool
    is_top_risk: bool
    evidence: str


class IncidentAlarm(AlarmRecord):
    sensor_name: str


class TrendSignal(BaseModel):
    sensor_id: str
    measurement_name: str
    signal_id: str
    unit: str


class TrendWindow(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime
    signals: list[TrendSignal]

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class IncidentDetail(IncidentSummary):
    as_of: datetime
    candidates: list[IncidentCandidate]
    alarms: list[IncidentAlarm]
    trend_window: TrendWindow
    data_coverage: Literal["full", "partial", "none"]
    warnings: list[str]


class IncidentReportDraft(BaseModel):
    incident_id: str
    equipment_id: str
    title: str
    symptom: str
    cause: str = Field(description="원인 후보는 검토 항목이며 확정 원인이 아니다.")
    action: str
    risk: str
    suspected_error_type_ids: list[str]
