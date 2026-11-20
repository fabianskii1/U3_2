import { z } from "zod";

export const causeCandidateSchema = z.object({
  id: z.string(),
  label: z.string(),
  rank: z.number(),
  probability: z.number().nullable(),
});
export const sourceLinkSchema = z.object({
  id: z.string(),
  title: z.string(),
  href: z.string(),
});
export const inspectionSchema = z.object({
  id: z.string(),
  candidateId: z.string(),
  method: z.string(),
  checkedAt: z.string(),
  result: z.string(),
  evidenceId: z.string(),
  evidenceUrl: z.string(),
});
export const reportSensorSchema = z.object({
  id: z.string(),
  name: z.string(),
  unit: z.string(),
  baseline: z.number().nullable(),
  observed: z.number().nullable(),
  points: z
    .array(z.object({ time: z.string(), value: z.number().nullable() }))
    .optional(),
});
export const maintenanceReportSchema = z.object({
  schemaVersion: z.literal(1),
  status: z.enum(["draft", "review", "confirmed"]),
  createdAt: z.string(),
  original: z.object({
    kind: z.enum(["connected", "example", "manual"]),
    capturedAt: z.string(),
    alarm: z
      .object({
        id: z.string(),
        equipmentId: z.string(),
        sensorId: z.string(),
        occurredAt: z.string(),
        value: z.number().nullable(),
        threshold: z.number().nullable(),
        unit: z.string(),
        reason: z.string(),
      })
      .nullable(),
    aiCandidates: z.array(causeCandidateSchema),
    sensors: z.array(reportSensorSchema),
    legacyCause: z.string(),
    legacyAction: z.string(),
    referenceNotes: z.array(z.string()).optional(),
  }),
  incident: z.object({
    eventId: z.string(),
    equipmentName: z.string(),
    alarmId: z.string(),
    alarmAt: z.string(),
    sensorIds: z.array(z.string()),
    operatingConditions: z.string(),
    location: z.string(),
    manufacturer: z.string(),
    model: z.string(),
    recentMaintenance: z.string(),
  }),
  observations: z.object({ symptoms: z.string(), impact: z.string() }),
  diagnosis: z.object({
    candidateChecks: z.record(
      z.string(),
      z.enum(["unverified", "checking", "excluded", "verified"]),
    ),
    inspections: z.array(inspectionSchema),
    final: z.object({
      candidateId: z.string().nullable(),
      otherCause: z.string(),
      rationale: z.string(),
      confirmedAt: z.string().nullable(),
    }),
  }),
  manuals: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      revision: z.string(),
      section: z.string(),
      recommendation: z.string(),
      href: z.string(),
    }),
  ),
  work: z.object({
    orderId: z.string(),
    worker: z.string(),
    startedAt: z.string(),
    completedAt: z.string(),
    description: z.string(),
    parts: z.string(),
  }),
  review: z.object({
    csvRange: z.string(),
    evidence: z.array(sourceLinkSchema),
    pastCaseIds: z.string(),
    recorder: z.string(),
    reviewer: z.string(),
    registeredAt: z.string(),
    state: z.enum(["pending", "reviewing", "reviewed"]),
  }),
  confirmedAt: z.string().nullable(),
  revisions: z.array(
    z.object({ at: z.string(), reason: z.string(), snapshot: z.string() }),
  ),
});

export type MaintenanceReport = z.infer<typeof maintenanceReportSchema>;
export type CauseCandidate = z.infer<typeof causeCandidateSchema>;
export type ReportSensor = z.infer<typeof reportSensorSchema>;
export type Inspection = z.infer<typeof inspectionSchema>;
