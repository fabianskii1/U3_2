import { afterEach, expect, it } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import { useSelectionStore } from "../../features/hierarchy/index.ts";
import { SelectionUrlSync } from "./SelectionUrlSync.tsx";

afterEach(() => {
  cleanup();
  useSelectionStore.getState().setSelection({
    plantId: null,
    unitId: null,
    equipmentId: null,
  });
});

it("저장된 View의 계층 선택을 전역 상태로 동기화한다", async () => {
  const { rerender } = render(
    <SelectionUrlSync
      selection={{ plantId: "P-01", unitId: "P-01-P1", equipmentId: "P-1101A" }}
    />,
  );
  await waitFor(() =>
    expect(useSelectionStore.getState()).toMatchObject({
      plantId: "P-01",
      unitId: "P-01-P1",
      equipmentId: "P-1101A",
    }),
  );
  rerender(
    <SelectionUrlSync
      selection={{ plantId: "P-01", unitId: "P-01-P1", equipmentId: null }}
    />,
  );
  await waitFor(() =>
    expect(useSelectionStore.getState().equipmentId).toBeNull(),
  );
});
