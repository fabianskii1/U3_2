import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { create } from "zustand";
import { devtools } from "zustand/middleware";

import type { SensorInterval } from "./trend-interval.ts";

type TrendContext = {
  sensor_id: string | null;
  sensor_interval: SensorInterval | null;
  sensor_start_time: string | null;
  sensor_end_time: string | null;
};

const emptyContext: TrendContext = {
  sensor_id: null,
  sensor_interval: null,
  sensor_start_time: null,
  sensor_end_time: null,
};

export const useTrendStore = create<
  TrendContext & {
    setContext: (context: TrendContext) => void;
    reset: () => void;
  }
>()(
  devtools(
    (set) => ({
      ...emptyContext,
      setContext: (context) => set(context, false, "trend/setContext"),
      reset: () => set(emptyContext, false, "trend/reset"),
    }),
    devtoolsOptions("Trend"),
  ),
);
