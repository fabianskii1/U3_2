import { Input } from "./input.tsx";
export function DateRangePicker({
  from,
  to,
  onChange,
  withTime = false,
}: {
  withTime?: boolean;
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}) {
  return (
    <div className={withTime ? "date-range date-range-time" : "date-range"}>
      <label>
        <span className="sr-only">시작 일자</span>
        <Input
          aria-label="시작 일자"
          type={withTime ? "datetime-local" : "date"}
          step={withTime ? 1 : undefined}
          value={from}
          max={to || undefined}
          onChange={(e) => onChange(e.target.value, to)}
        />
      </label>
      <span className="muted">—</span>
      <label>
        <span className="sr-only">종료 일자</span>
        <Input
          aria-label="종료 일자"
          type={withTime ? "datetime-local" : "date"}
          step={withTime ? 1 : undefined}
          value={to}
          min={from || undefined}
          onChange={(e) => onChange(from, e.target.value)}
        />
      </label>
    </div>
  );
}
