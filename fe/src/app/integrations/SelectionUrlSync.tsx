import { useEffect } from "react";
import { useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import {
  hierarchyQuery,
  useSelectionStore,
} from "../../features/hierarchy/index.ts";
import { resolveSelection } from "../router/navigation.ts";
export function SelectionUrlSync() {
  const [params] = useSearchParams();
  const { data } = useQuery(hierarchyQuery);
  const set = useSelectionStore((s) => s.setSelection);
  useEffect(() => {
    if (data) set(resolveSelection(params, data));
  }, [params, data, set]);
  return null;
}
