import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { hierarchy } from "../../../../mock/fixtures.ts";
import type { Selection } from "../model/hierarchy.schema.ts";
import { HierarchyFilters } from "./HierarchyFilters.tsx";

afterEach(cleanup);

it("설비 센서를 context-bar에서 여러 개 선택하고 해제한다", () => {
  function Filters() {
    const [selection, setSelection] = useState<Selection>({
      plantId: "P-01",
      unitId: "P-01-P1",
      equipmentId: "P-1101A",
      sensorIds: ["P1101A-VIB", "P1101A-TEMP"],
    });
    return (
      <HierarchyFilters
        data={hierarchy}
        selection={selection}
        onSelect={setSelection}
      />
    );
  }
  render(<Filters />);
  fireEvent.click(screen.getByLabelText("Sensor 선택"));
  const vibration = screen.getByRole("checkbox", { name: /P1101A-VIB/ });
  const temperature = screen.getByRole("checkbox", { name: /P1101A-TEMP/ });
  const pressure = screen.getByRole("checkbox", { name: /P1101A-PRES/ });
  expect(vibration).toBeChecked();
  expect(temperature).toBeChecked();
  expect(pressure).not.toBeChecked();
  fireEvent.click(pressure);
  fireEvent.click(vibration);
  expect(pressure).toBeChecked();
  expect(vibration).not.toBeChecked();
  expect(screen.getByText("2 / 3개 선택")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "전체 해제" }));
  expect(screen.getByText("0 / 3개 선택")).toBeInTheDocument();
  expect(pressure).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "전체 선택" }));
  expect(screen.getByText("3 / 3개 선택")).toBeInTheDocument();
  expect(vibration).toBeChecked();
  expect(temperature).toBeChecked();
  expect(pressure).toBeChecked();
});
