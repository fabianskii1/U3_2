import { z } from "zod";
import { reportFieldsSchema, reportPatchSchema } from "./report.ts";
export const chatRequestSchema = z.object({
  message: z.string().min(1).max(5000),
  sessionId: z.string(),
  screenContext: z.object({
    page: z.string(),
    query: z.string().optional(),
    section: z.string().optional(),
    incidentId: z.string().optional(),
    asOf: z.string().optional(),
    replayHour: z.number().nullable().optional(),
    replayMax: z.number().optional(),
    plantId: z.string().nullable().optional(),
    unitId: z.string().nullable().optional(),
    equipmentId: z.string().nullable(),
    sensor: z.string().optional(),
    sensorId: z.string().optional(),
    sensorIds: z.array(z.string()).optional(),
    alarmId: z.string().optional(),
    trendSeries: z
      .array(
        z.object({
          sensorId: z.string(),
          start: z.string(),
          end: z.string(),
          label: z.string().optional(),
        }),
      )
      .optional(),
    sensor_interval: z.string().optional(),
    from: z.string().optional(),
    to: z.string().optional(),
  }),
  reportContext: z
    .object({
      reportId: z.string(),
      equipmentId: z.string(),
      localRevision: z.number(),
      values: reportFieldsSchema,
    })
    .optional(),
});
export const chatResponseSchema = z.object({
  message: z.string(),
  choices: z
    .array(z.object({ label: z.string(), message: z.string() }))
    .optional(),
  action: z
    .discriminatedUnion("type", [
      z.object({ type: z.literal("navigate"), href: z.string() }),
      z.object({
        type: z.literal("create-draft"),
        equipmentId: z.string(),
        values: reportFieldsSchema,
      }),
      z.object({
        type: z.literal("patch-draft"),
        reportId: z.string(),
        baseLocalRevision: z.number(),
        patch: reportPatchSchema,
      }),
      z.object({ type: z.literal("save-draft"), reportId: z.string() }),
    ])
    .optional(),
  links: z.array(z.object({ title: z.string(), href: z.string() })).optional(),
});
export type ChatRequest = z.infer<typeof chatRequestSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;
