import { describe, expect, it } from "vitest";
import {
  formatGap,
  levelLabel,
  levelTone,
  splitEvidence,
  timeline,
} from "./incident.ts";
import {
  incidentDetailSchema,
  incidentListSchema,
} from "../../../shared/api/contracts/incident.ts";
import { snapTime } from "../../trend/ui/TrendChart.tsx";
import { getIncident, listIncidents } from "../../../../mock/incidents.ts";

const summary = {
  incident_id: "INC-P3-202611081300",
  plant_id: "PLANT-01",
  equipment_group_id: "CDU-01",
  equipment_id: "P3",
  equipment_name: "3번 펌프",
  status: "closed",
  incident_start_time: "2026-11-08T04:00:00+00:00",
  detect_time: "2026-11-08T15:59:00+00:00",
  first_alarm_time: "2026-11-18T23:00:00+00:00",
  incident_end_time: "2026-11-19T10:30:00+00:00",
  peak_level: 2,
  lead_sensor_id: "10-PT-1307",
  lead_sensor_name: "토출압",
  diagnosis: "임펠러 마모",
  top_risk_fault: "임펠러 마모",
  top_cof: 1,
  top_pof: 0.033,
  incident_score: 0.4,
  alarm_grade: "낮음",
  grade_reason: "작음 × 24시간 이상",
  response_time_h: 203.4,
  actionable: true,
  alarm_count: 2,
  linked_alarm_count: 2,
  trend_count: 3,
} as const;

describe("incident model", () => {
  it("splits analyzer evidence on the slash separator only", () => {
    expect(
      splitEvidence(
        "차압 -33 % / 전류 -14 % / 진동·전류가 같이 흔들림, 흡입 조건은 정상 (동력 전달 불안정)",
      ),
    ).toEqual([
      "차압 -33 %",
      "전류 -14 %",
      "진동·전류가 같이 흔들림, 흡입 조건은 정상 (동력 전달 불안정)",
    ]);
  });

  it("formats gaps and ignores missing or reversed times", () => {
    expect(formatGap("2026-11-19T00:00:00Z", "2026-11-19T00:59:00Z")).toBe(
      "59분",
    );
    expect(formatGap("2026-11-08T04:00:00Z", "2026-11-18T23:00:00Z")).toBe(
      "10일 19시간",
    );
    expect(formatGap("2026-11-19T00:00:00Z", null)).toBeNull();
    expect(
      formatGap("2026-11-19T00:00:00Z", "2026-11-18T00:00:00Z"),
    ).toBeNull();
  });

  it("builds a timeline and labels the end by status", () => {
    const steps = timeline(
      incidentListSchema.parse({
        as_of: "2026-11-20T00:00:00Z",
        items: [summary],
        next_cursor: null,
      }).items[0],
    );
    expect(steps.map((step) => step.label)).toEqual([
      "사건 시작",
      "감지",
      "첫 알람",
      "종료",
    ]);
    expect(steps[2].gap).toBe("10일 7시간");
    const ongoing = timeline({
      ...summary,
      status: "ongoing",
      first_alarm_time: null,
    });
    expect(ongoing[2]).toMatchObject({ time: null, gap: null });
    expect(ongoing[3].label).toBe("예상 종료");
    expect(ongoing[3].gap).toBe("10일 18시간");
  });

  it("maps levels to labels and existing badge tones", () => {
    expect([
      levelLabel(3),
      levelLabel(null),
      levelTone(3),
      levelTone(2),
    ]).toEqual(["위험", "미기록", "High", "Medium"]);
  });
});

describe("incident contracts", () => {
  it("parses a backend detail with nullable alarm fields", () => {
    const detail = incidentDetailSchema.parse({
      ...summary,
      as_of: "2026-11-20T00:00:00Z",
      candidates: [
        {
          rank: 1,
          error_type_id: "5",
          fault: "임펠러 마모",
          rule_score_s: 5,
          s_top3_sum: 5,
          p: 1,
          speed: 1,
          impact: 1,
          w: 1,
          cof: 1,
          p_trend: 0,
          pf_hours: 720,
          p_pf: 0.033,
          pof: 0.033,
          score: 0.4,
          is_diagnosis: true,
          is_top_risk: true,
          evidence: "차압 -33 %",
        },
      ],
      alarms: [
        {
          alarm_id: "84",
          source_alarm_id: "AL-P3-PD-LO-202611190800",
          equipment_id: "P3",
          sensor_id: "10-PT-1307",
          sensor_name: "토출압",
          setpoint_id: "SP-10-PT-1307-LOW-WARNING-V1",
          alarm_type: "Setpoint",
          event_type: "예측",
          alarm_level: 2,
          peak_level: 2,
          alarm_start_time: "2026-11-18T23:00:00Z",
          alarm_end_time: "2026-11-19T10:29:00Z",
          sensor_start_time: null,
          sensor_end_time: null,
          is_active: null,
          cof_score: 1,
          unit: "kPa(g)",
          user_message: "예측",
          incident_id: "INC-P3-202611081300",
        },
      ],
      trend_window: {
        from: "2026-11-07T04:00:00Z",
        to: "2026-11-19T16:30:00Z",
        signals: [
          {
            sensor_id: "10-PT-1307",
            measurement_name: "토출압",
            signal_id: "10-PT-1307",
            unit: "kPa(g)",
          },
        ],
      },
      data_coverage: "full",
      warnings: [],
    });
    expect(detail.alarms[0].sensor_start_time).toBeNull();
  });
});

describe("trend incident overlay", () => {
  const points = [
    { time: "2026-11-19T00:00:00Z" },
    { time: "2026-11-19T01:00:00Z" },
    { time: "2026-11-19T02:00:00Z" },
  ];
  it("snaps instants onto plotted categories", () => {
    expect(snapTime(points, "2026-11-19T00:30:00Z", "start")).toBe(
      "2026-11-19T01:00:00Z",
    );
    expect(snapTime(points, "2026-11-19T01:30:00Z", "end")).toBe(
      "2026-11-19T01:00:00Z",
    );
    expect(snapTime(points, "2026-11-18T00:00:00Z", "start")).toBe(
      "2026-11-19T00:00:00Z",
    );
    expect(snapTime(points, "2026-11-20T00:00:00Z", "start")).toBeNull();
    expect(snapTime(points, "2026-11-18T00:00:00Z", "end")).toBeNull();
    expect(snapTime([], "2026-11-19T00:00:00Z", "start")).toBeNull();
  });
});

describe("mock incident api", () => {
  it("returns contract-valid data and honours filters", () => {
    const now = Date.parse("2026-11-19T08:00:00Z");
    const all = incidentListSchema.parse(
      listIncidents(now, new URLSearchParams()),
    );
    expect(all.items).toHaveLength(2);
    const ongoing = listIncidents(now, new URLSearchParams("status=ongoing"));
    expect(ongoing.items.map((item) => item.incident_id)).toEqual([
      "INC-DEMO-1101A",
    ]);
    const detail = incidentDetailSchema.parse(
      getIncident(now, "INC-DEMO-1101A"),
    );
    expect(detail.candidates[0].is_diagnosis).toBe(true);
    expect(getIncident(now, "missing")).toBeUndefined();
  });
});
