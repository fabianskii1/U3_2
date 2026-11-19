import { z } from "zod";
export const alarmSchema = z.object({
  id: z.string(),
  equipmentId: z.string(),
  tagId: z.string(),
  signal: z.string(),
  severity: z.enum(["High", "Medium", "Low"]),
  value: z.number().optional(),
  limit: z.number().optional(),
  unit: z.string(),
  occurredAt: z.string(),
  type: z.string(),
  eventType: z.enum(["예측", "임계치 초과"]).optional(),
  alarmLevel: z.number().int().min(0).max(4).optional(),
  reason: z.string(),
});
export const alarmsResponseSchema = z.object({
  alarms: z.array(alarmSchema),
  asOf: z.string(),
  sequence: z.number(),
  cursor: z.string().optional(),
});
export type Alarm = z.infer<typeof alarmSchema>;
