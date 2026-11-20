import { expect, test } from "vitest";
import { hierarchy } from "../../../../mock/fixtures.ts";
import { getIncident, incidentDraft } from "../../../../mock/incidents.ts";
import { incidentReportFields } from "./incident-report.ts";
import { reportFieldsSchema } from "./report.schema.ts";
import { useReportDraftStore } from "./report-draft.store.ts";

const now = Date.parse("2026-11-20T00:00:00Z");
const incident = getIncident(now, "INC-DEMO-1101A")!;
const draft = incidentDraft(now, incident.incident_id)!;
const equipment = hierarchy.equipment.find(
  (asset) => asset.id === incident.equipment_id,
)!;

test("incident facts, candidate evidence, sensors and references survive report serialization", () => {
  const values = incidentReportFields(incident, draft, equipment, {
    location: "CDU",
    manuals: [
      {
        id: "M1",
        title: "펌프 매뉴얼",
        href: "/equip?equip_id=P1",
        revision: "",
        section: "",
        recommendation: "",
      },
    ],
    history: "점검 이력",
    historyIds: "H1",
    notes: [],
  });
  const persisted = reportFieldsSchema.parse(
    JSON.parse(JSON.stringify(values)),
  );
  expect(persisted.symptom).toBe(draft.symptom);
  expect(persisted.cause).toBe(draft.cause);
  expect(persisted.action).toBe(draft.action);
  expect(persisted.risk).toBe(draft.risk);
  const report = persisted.maintenance!;
  expect(report.incident.eventId).toBe(incident.incident_id);
  expect(report.incident.alarmId).toBe(incident.alarms[0].alarm_id);
  expect(
    report.original.aiCandidates.map((candidate) => candidate.label),
  ).toEqual(incident.candidates.map((candidate) => candidate.fault));
  expect(report.original.incident?.candidates[0].evidence).toBe(
    incident.candidates[0].evidence,
  );
  expect(report.original.incident?.trend_window).toEqual(incident.trend_window);
  expect(report.original.sensors.map((sensor) => sensor.id)).toContain(
    incident.lead_sensor_id,
  );
  expect(report.manuals[0].id).toBe("M1");
  expect(report.incident.recentMaintenance).toBe("점검 이력");
  expect(
    report.review.evidence.some((item) => item.href.endsWith("section=trend")),
  ).toBe(true);
  expect(report.diagnosis.final.confirmedAt).toBeNull();
  expect(
    Object.values(report.diagnosis.candidateChecks).every(
      (value) => value === "unverified",
    ),
  ).toBe(true);
  expect(report.work.description).toBe("");
  expect(report.work.worker).toBe("");
  expect(report.status).toBe("draft");
});

test("the transferred draft can be edited and cancelled without losing the original transfer", () => {
  const { maintenance, ...fields } = incidentReportFields(
    incident,
    draft,
    equipment,
  );
  const store = useReportDraftStore.getState();
  const id = store.createDraft(equipment.id, fields);
  store.initializeMaintenance(id, maintenance);
  store.patch(id, { symptom: "변경한 증상" });
  store.restoreSaved(id);
  expect(useReportDraftStore.getState().drafts[id].values.symptom).toBe(
    draft.symptom,
  );
  expect(
    useReportDraftStore.getState().drafts[id].values.maintenance?.original
      .incident?.incident_id,
  ).toBe(incident.incident_id);
});

test("a draft from another incident cannot be copied into this equipment", () => {
  expect(() =>
    incidentReportFields(
      incident,
      { ...draft, equipment_id: "other" },
      equipment,
    ),
  ).toThrow("일치하지 않습니다");
});
