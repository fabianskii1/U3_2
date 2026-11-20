import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { ArrowRight } from "lucide-react";
import {
  incidentsQuery,
  type IncidentFilters,
} from "../api/incidents.queries.ts";
import { IncidentRow } from "./IncidentCard.tsx";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { Button } from "../../../shared/ui/button.tsx";
import { LoadingState } from "../../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../../shared/ui/ErrorState.tsx";
import { errorMessage } from "../../../shared/api/http-client.ts";

/** Incidents for a scope; load failures are never shown as "no incidents". */
export function IncidentPanel({
  title,
  description,
  filters,
  emptyText,
  moreHref = "/incidents",
}: {
  title: string;
  description: string;
  filters: IncidentFilters;
  emptyText: string;
  moreHref?: string;
}) {
  const query = useQuery(incidentsQuery({ limit: 5, ...filters }));
  return (
    <Card className="incident-panel">
      <CardHeader
        title={title}
        description={description}
        action={
          <Button asChild variant="ghost" size="sm">
            <Link to={moreHref}>
              전체 보기
              <ArrowRight size={14} />
            </Link>
          </Button>
        }
      />
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          message={`사건을 조회하지 못했습니다. ${errorMessage(query.error)}`}
          retry={() => void query.refetch()}
        />
      ) : query.data.items.length ? (
        query.data.items.map((incident) => (
          <IncidentRow key={incident.incident_id} incident={incident} />
        ))
      ) : (
        <p className="empty-state">{emptyText}</p>
      )}
    </Card>
  );
}
