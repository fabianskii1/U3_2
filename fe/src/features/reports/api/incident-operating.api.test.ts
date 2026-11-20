import { afterEach, expect, test, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { http } from "../../../shared/api/http-client.ts";
import { hierarchy } from "../../../../mock/fixtures.ts";
import { getIncident } from "../../../../mock/incidents.ts";
import { incidentOperatingQuery } from "./incident-operating.api.ts";
import { reportReferencesQuery } from "./report-references.api.ts";

const incident = getIncident(
  Date.parse("2026-11-20T00:00:00Z"),
  "INC-DEMO-1101A",
)!;
const equipment = hierarchy.equipment.find(
  (row) => row.id === incident.equipment_id,
)!;
afterEach(() => vi.restoreAllMocks());

test("historical conditions discard future, stale and missing values instead of using current readings", async () => {
  const at = Date.parse(incident.first_alarm_time!);
  vi.spyOn(http, "get").mockImplementation(async (_url, config) => {
    const params = config?.params as Record<string, unknown>;
    expect(params.interval).toBe("1m");
    expect(Date.parse(String(params.to))).toBe(at + 1);
    return {
      data: {
        unit: "rpm",
        points: [
          { time: new Date(at - 600000).toISOString(), value: 111 },
          { time: new Date(at - 60000).toISOString(), value: 1450 },
          { time: new Date(at + 60000).toISOString(), value: 9999 },
          { time: new Date(at).toISOString(), value: null },
        ],
      },
    };
  });
  const client = new QueryClient();
  const result = await client.fetchQuery(
    incidentOperatingQuery(incident, equipment),
  );
  expect(result.readings.length).toBe(equipment.tags.length);
  expect(result.readings.every((row) => row.value === 1450)).toBe(true);
  expect(result.readings.every((row) => Date.parse(row.measuredAt) <= at)).toBe(
    true,
  );
  client.clear();
});

test("missing and failed sensors are distinguished and never replaced by zero", async () => {
  vi.spyOn(http, "get").mockImplementation(async (_url, config) => {
    if ((config?.params as Record<string, unknown>).sensor_id === equipment.tags[0].id)
      throw new Error("offline");
    return { data: { unit: "rpm", points: [] } };
  });
  const client = new QueryClient();
  const result = await client.fetchQuery(
    incidentOperatingQuery(incident, equipment),
  );
  expect(result.readings).toEqual([]);
  expect(result.failed).toEqual([equipment.tags[0].name]);
  expect(result.missing.length).toBe(equipment.tags.length - 1);
  client.clear();
});

test("pump metadata never takes manufacturer or model from a sensor and history is bounded to the incident", async () => {
  vi.spyOn(http, "get").mockImplementation(async (url, config) => {
    if (url === "/maintenance-histories") {
      expect((config?.params as Record<string, unknown>).to).toBe(incident.first_alarm_time);
      return { data: { items: [] } };
    }
    if (String(url).endsWith("/manuals")) return { data: [] };
    return {
      data: {
        location: null,
        sensors: [
          { manufacturer: "Sensor Vendor", model_name: "Sensor Model" },
        ],
      },
    };
  });
  const client = new QueryClient();
  const refs = await client.fetchQuery(
    reportReferencesQuery(equipment.id, incident.first_alarm_time!),
  );
  expect(refs.location).toBe("");
  expect(refs.manufacturer).toBe("");
  expect(refs.model).toBe("");
  expect(refs.fieldNotes?.manufacturer).toContain("펌프 제조사 미등록");
  expect(refs.history).toContain("정비 이력 없음");
  client.clear();
});
