import { z } from "zod";
export const tagSchema = z.object({
  id: z.string(),
  signal: z.string(),
  name: z.string(),
  unit: z.string(),
  limit: z.number().optional(),
  base: z.number().optional(),
  sensorLevel: z.number().nullable().optional(),
  currentValue: z.number().nullable().optional(),
  measuredAt: z.string().nullable().optional(),
});
export const equipmentSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  grade: z.string(),
  equipmentLevel: z.number().optional(),
  equipmentStatus: z.number().int().min(0).max(4).optional(),
  unitId: z.string(),
  plantId: z.string(),
  tags: z.array(tagSchema),
});
export const hierarchySchema = z.object({
  plants: z.array(
    z.object({ id: z.string(), name: z.string(), location: z.string() }),
  ),
  units: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      plantId: z.string(),
      processType: z.string().nullable(),
    }),
  ),
  equipment: z.array(equipmentSchema),
});
export type Hierarchy = z.infer<typeof hierarchySchema>;
export type Equipment = z.infer<typeof equipmentSchema>;
export type Selection = {
  plantId: string | null;
  unitId: string | null;
  equipmentId: string | null;
  sensorIds: string[];
};
