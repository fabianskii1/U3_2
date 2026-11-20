import { Link } from "react-router";
import { ArrowUpRight } from "lucide-react";
import type { IncidentSummary } from "../../../shared/api/contracts/incident.ts";
import { Badge } from "../../../shared/ui/badge.tsx";
import { dateTime } from "../../../shared/lib/date-time.ts";
import { STATUS_LABELS, levelLabel, levelTone } from "../model/incident.ts";

export function IncidentRow({ incident }: { incident: IncidentSummary }) {
  return (
    <Link
      to={`/incidents/${encodeURIComponent(incident.incident_id)}`}
      className="priority-row incident-row"
    >
      <Badge tone={levelTone(incident.peak_level)}>
        {levelLabel(incident.peak_level)}
      </Badge>
      <div className="priority-text">
        <strong>
          {incident.equipment_name} · {incident.diagnosis}
          <span className="muted"> (추정)</span>
        </strong>
        <span>
          {STATUS_LABELS[incident.status]} ·{" "}
          {dateTime(incident.incident_start_time)} 시작 · 대응{" "}
          {incident.alarm_grade}
        </span>
      </div>
      <ArrowUpRight size={15} />
    </Link>
  );
}
