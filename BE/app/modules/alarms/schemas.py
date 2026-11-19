from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AlarmEventType = Literal["예측", "임계치 초과"]
PriorityGroup = Literal["equipment", "alarm"]
PriorityStatus = Literal["ok", "unscored", "unavailable", "empty", "no_data"]


class AlarmRecord(BaseModel):
    alarm_id: str
    source_alarm_id: str | None
    equipment_id: str
    sensor_id: str
    setpoint_id: str | None
    alarm_type: str
    event_type: AlarmEventType | None
    alarm_level: int
    alarm_start_time: datetime
    alarm_end_time: datetime | None = Field(description="조치 완료 시각")
    sensor_start_time: datetime | None
    sensor_end_time: datetime | None
    is_active: bool | None = Field(description="활성 여부. null은 상태 미확인.")
    cof_score: float | None
    unit: str
    user_message: str


class AlarmHistory(BaseModel):
    items: list[AlarmRecord]
    next_cursor: str | None


class RankedAlarm(AlarmRecord):
    rank: int
    equipment_name: str
    sensor_name: str
    reason: str
    has_initial_report: bool
    equipment_active_count: int
    prediction_count: int
    threshold_exceeded_count: int
    condition_count: int = Field(description="해당 설비의 활성 센서·setpoint 조합 수")


class AlarmPrioritySummary(BaseModel):
    status: PriorityStatus = Field(
        description="ok: 순위 있음, unscored: 활성 알람 점수 미평가, "
        "unavailable: 활성 여부 미확인, empty: 활성 0건, no_data: 조회 범위에 이력 없음"
    )
    as_of: datetime = Field(description="순위 산정 기준 시각")
    group_by: PriorityGroup
    active_count: int = Field(description="조회 범위의 활성 알람 행 수. 미평가 포함.")
    unscored_count: int = Field(description="활성 알람 중 CoF 미평가 행 수")
    unknown_count: int = Field(description="활성 여부를 확인할 수 없는 알람 행 수")
    affected_equipment_count: int = Field(description="활성 알람이 있는 설비 수")
    condition_count: int = Field(description="조회 범위의 활성 설비·센서·setpoint 조합 수")


class AlarmPriorities(AlarmPrioritySummary):
    items: list[RankedAlarm]


class IntakePriority(AlarmPrioritySummary):
    plant_id: str
    selected_alarm_id: str | None


class AlarmIntakeResult(BaseModel):
    alarm: AlarmRecord
    closed_alarm_id: str | None
    priority: IntakePriority
    initial_report: dict | None
