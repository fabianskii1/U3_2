import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import { incidentsQuery } from "../../incidents/api/incidents.queries.ts";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { faultParts, pumpParts } from "./pump3d.config.ts";

type ViewMode = "all" | "ghost" | "only";
type PartMesh = {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  base: THREE.Color;
};
type Viewer = {
  groups: Record<string, PartMesh[]>;
  update: (
    red: string[],
    amber: string[],
    pulse: boolean,
    mode: ViewMode,
  ) => void;
};

const MODEL_URL = `${import.meta.env.BASE_URL}models/cdu_pump_skid_etanorm_125-100-315.glb`;

function normalize(value: string) {
  return value.replace(/\s/g, "_").replace(/[\[\].:/]/g, "");
}

function partFor(mesh: THREE.Object3D): string | undefined {
  let names = "";
  for (let item: THREE.Object3D | null = mesh; item; item = item.parent)
    names += ` ${item.name}`;
  const normalized = normalize(names);
  return Object.keys(pumpParts).find((key) =>
    pumpParts[key].match.some((term) => normalized.includes(normalize(term))),
  );
}

function PumpModel({
  red,
  amber,
  pulse,
  mode,
}: {
  red: string[];
  amber: string[];
  pulse: boolean;
  mode: ViewMode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const currentView = useRef({ red, amber, pulse, mode });
  currentView.current = { red, amber, pulse, mode };
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const host = container.current;
    if (!host) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setError("이 기기에서는 3D(WebGL)를 사용할 수 없습니다.");
      setLoading(false);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const environmentGenerator = new THREE.PMREMGenerator(renderer);
    const environment = environmentGenerator.fromScene(
      new RoomEnvironment(),
      0.04,
    );
    scene.environment = environment.texture;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(2, 3, 2);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.8);
    fill.position.set(-2, 1, -1.5);
    scene.add(fill);
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 50);
    camera.position.set(1.2, 0.8, 1.42);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    const groups: Record<string, PartMesh[]> = {};
    let model: THREE.Group | null = null;
    let frame = 0;
    let disposed = false;
    let hot: PartMesh[] = [];
    let blink = false;
    let lastFocus = "";
    let homePosition = camera.position.clone();
    let homeTarget = controls.target.clone();

    const resize = () => {
      const width = host.clientWidth,
        height = host.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    const animate = (time: number) => {
      frame = requestAnimationFrame(animate);
      controls.update();
      const strength = blink
        ? 0.12 + 0.35 * (0.5 + 0.5 * Math.sin(time / 260))
        : 0.12;
      for (const part of hot) part.material.emissive.setRGB(strength, 0, 0);
      renderer.render(scene, camera);
    };
    frame = requestAnimationFrame(animate);

    new GLTFLoader().load(
      MODEL_URL,
      (gltf) => {
        if (disposed) return;
        model = gltf.scene;
        model.traverse((object) => {
          if (!(object instanceof THREE.Mesh)) return;
          const original = Array.isArray(object.material)
            ? object.material[0]
            : object.material;
          const color =
            original instanceof THREE.MeshStandardMaterial
              ? original.color.clone()
              : new THREE.Color(0x8a95a3);
          const material = new THREE.MeshStandardMaterial({
            color,
            metalness: 0.25,
            roughness: 0.45,
            side: THREE.DoubleSide,
          });
          object.material = material;
          const part = partFor(object);
          if (part)
            (groups[part] ??= []).push({ mesh: object, material, base: color });
        });
        scene.add(model);
        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const radius = box.getSize(new THREE.Vector3()).length() / 2;
        const distance =
          (radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))) * 0.7;
        camera.near = distance / 200;
        camera.far = distance * 20;
        camera.position
          .copy(center)
          .add(
            new THREE.Vector3(-0.6, 0.42, 0.68)
              .normalize()
              .multiplyScalar(distance),
          );
        camera.updateProjectionMatrix();
        controls.target.copy(center);
        controls.update();
        homePosition = camera.position.clone();
        homeTarget = center.clone();
        setLoading(false);
        viewer.current = {
          groups,
          update(nextRed, nextAmber, nextPulse, nextMode) {
            const redSet = new Set(nextRed),
              amberSet = new Set(nextAmber);
            const hasHot = redSet.size + amberSet.size > 0;
            hot = [];
            blink = nextPulse;
            for (const [part, meshes] of Object.entries(groups)) {
              const isRed = redSet.has(part),
                isAmber = !isRed && amberSet.has(part);
              for (const item of meshes) {
                item.material.color.copy(
                  isRed
                    ? new THREE.Color(0xe53b35)
                    : isAmber
                      ? new THREE.Color(0xf59e00)
                      : item.base,
                );
                item.material.emissive.set(0);
                item.mesh.visible =
                  nextMode !== "only" || !hasHot || isRed || isAmber;
                const ghost =
                  nextMode === "ghost" && hasHot && !isRed && !isAmber;
                item.material.transparent = ghost;
                item.material.opacity = ghost ? 0.12 : 1;
                item.material.depthWrite = !ghost;
                if (isRed) hot.push(item);
              }
            }
            const focusKey = `${nextMode}|${[...redSet].sort().join(",")}|${[...amberSet].sort().join(",")}`;
            if (focusKey !== lastFocus) {
              lastFocus = focusKey;
              const focused = Object.entries(groups)
                .filter(([part]) => redSet.has(part) || amberSet.has(part))
                .flatMap(([, meshes]) => meshes);
              if (nextMode === "all" || !focused.length) {
                camera.position.copy(homePosition);
                controls.target.copy(homeTarget);
              } else {
                const bounds = new THREE.Box3();
                focused.forEach(({ mesh }) => bounds.expandByObject(mesh));
                const center = bounds.getCenter(new THREE.Vector3());
                const radius = Math.max(
                  bounds.getSize(new THREE.Vector3()).length() / 2,
                  0.08,
                );
                const distance =
                  (radius /
                    Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))) *
                  0.8;
                camera.position
                  .copy(center)
                  .add(
                    homePosition
                      .clone()
                      .sub(homeTarget)
                      .normalize()
                      .multiplyScalar(distance),
                  );
                controls.target.copy(center);
              }
              controls.update();
            }
          },
        };
        const latest = currentView.current;
        viewer.current.update(
          latest.red,
          latest.amber,
          latest.pulse,
          latest.mode,
        );
      },
      undefined,
      () => {
        if (!disposed) {
          setError("3D 모델을 읽지 못했습니다.");
          setLoading(false);
        }
      },
    );

    return () => {
      disposed = true;
      viewer.current = null;
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      model?.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return;
        object.geometry.dispose();
        const materials = Array.isArray(object.material)
          ? object.material
          : [object.material];
        materials.forEach((material) => material.dispose());
      });
      renderer.dispose();
      environment.dispose();
      environmentGenerator.dispose();
      host.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    viewer.current?.update(red, amber, pulse, mode);
  }, [red, amber, pulse, mode]);
  return (
    <div className="pump-3d-canvas" ref={container}>
      {error ? (
        <p className="muted small">{error}</p>
      ) : loading ? (
        <p className="muted small">3D 모델을 불러오는 중입니다.</p>
      ) : null}
    </div>
  );
}

function sensorPart(signal: string, name: string): string | null {
  const text = `${signal} ${name}`.toLowerCase();
  if (/pt.?101|흡입압|suction.pressure|\bps\b/.test(text)) return "pt101";
  if (/pt.?102|토출압|discharge.pressure|\bpd\b/.test(text)) return "pt102";
  if (/tt.?101|유체.?온도|fluid.temperature|\btf\b/.test(text)) return "tt101";
  return null;
}

export function Pump3D({
  equipment,
  alarms,
}: {
  equipment: Equipment;
  alarms: Alarm[];
}) {
  const [mode, setMode] = useState<ViewMode>("all");
  const incidentQuery = useQuery(
    incidentsQuery({ equipment_id: equipment.id, limit: 20 }),
  );
  const incident =
    incidentQuery.data?.items.find((item) => item.status === "ongoing") ?? null;
  const diagnosisParts = faultParts[incident?.diagnosis ?? ""] ?? [];
  const riskParts =
    incident && incident.top_risk_fault !== incident.diagnosis
      ? (faultParts[incident.top_risk_fault] ?? [])
      : [];
  const sensorHighlights = useMemo(
    () =>
      alarms
        .filter((alarm) => alarm.equipmentId === equipment.id)
        .map((alarm) => ({
          part: sensorPart(
            alarm.signal,
            equipment.tags.find((tag) => tag.id === alarm.tagId)?.name ?? "",
          ),
          level:
            alarm.alarmLevel ??
            ({ High: 3, Medium: 2, Low: 1 } as const)[alarm.severity],
          name:
            equipment.tags.find((tag) => tag.id === alarm.tagId)?.name ??
            alarm.signal,
        }))
        .filter((entry) => entry.part !== null),
    [alarms, equipment],
  );
  const red = [
    ...new Set([
      ...diagnosisParts,
      ...sensorHighlights
        .filter((item) => item.level >= 2)
        .map((item) => item.part!),
    ]),
  ];
  const amber = [
    ...new Set([
      ...riskParts,
      ...sensorHighlights
        .filter((item) => item.level === 1)
        .map((item) => item.part!),
    ]),
  ].filter((part) => !red.includes(part));
  const partNames = (parts: string[], color: "red" | "amber") =>
    parts.map((part) => (
      <span className={`pump-3d-part ${color}`} key={part}>
        {pumpParts[part]?.name ?? part}
      </span>
    ));

  return (
    <Card className="pump-3d-panel">
      <CardHeader
        title={`${equipment.id} 3D 부품`}
        description="고장 관련 부품과 센서 알람 위치를 표시합니다. 드래그로 회전하고 스크롤로 확대할 수 있습니다."
        action={
          <div
            className="pump-3d-modes"
            role="group"
            aria-label="3D 부품 표시 방식"
          >
            {(
              [
                ["all", "전체 보기"],
                ["ghost", "고장 부품 강조"],
                ["only", "고장 부품만"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={mode === value ? "is-active" : ""}
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
              >
                {label}
              </button>
            ))}
          </div>
        }
      />
      <div className="pump-3d-layout">
        <PumpModel
          red={red}
          amber={amber}
          pulse={red.length > 0 && (equipment.equipmentStatus ?? 0) >= 2}
          mode={mode}
        />
        <div className="pump-3d-info">
          <p>
            <strong>{equipment.name}</strong> ·{" "}
            {equipment.equipmentStatus ? "점검 필요" : "정상"}
          </p>
          {incidentQuery.isPending ? (
            <p className="muted small">진단 정보를 불러오는 중입니다.</p>
          ) : incidentQuery.isError ? (
            <p className="muted small">진단 정보를 불러오지 못했습니다.</p>
          ) : incident ? (
            <>
              <p>
                <strong>판별: {incident.diagnosis}</strong>
              </p>
              {diagnosisParts.length ? (
                <div className="pump-3d-parts">
                  {partNames(diagnosisParts, "red")}
                </div>
              ) : (
                <p className="muted small">
                  모델에서 대응하는 부품이 없습니다.
                </p>
              )}
              {riskParts.length > 0 && (
                <>
                  <p className="muted small">
                    위험 1위: {incident.top_risk_fault}
                  </p>
                  <div className="pump-3d-parts">
                    {partNames(
                      riskParts.filter(
                        (part) => !diagnosisParts.includes(part),
                      ),
                      "amber",
                    )}
                  </div>
                </>
              )}
              <p className="muted small">
                이상 시작{" "}
                {new Date(incident.incident_start_time).toLocaleString("ko-KR")}
              </p>
            </>
          ) : (
            <p className="muted small">진행 중인 이상 사건이 없습니다.</p>
          )}
          {sensorHighlights.length > 0 && (
            <>
              <p className="muted small">센서 알람 위치</p>
              <div className="pump-3d-parts">
                {sensorHighlights.map((item, index) => (
                  <span
                    key={`${item.part}-${index}`}
                    className={`pump-3d-part ${item.level >= 2 ? "red" : "amber"}`}
                  >
                    {item.name} · {pumpParts[item.part!]?.name}
                  </span>
                ))}
              </div>
            </>
          )}
          {mode !== "all" && red.length === 0 && amber.length === 0 && (
            <p className="muted small">
              강조할 부품이 없어 전체 모델을 보여줍니다.
            </p>
          )}
          <p className="muted small">
            임펠러는 케이싱 내부에 있어 케이싱으로 표시됩니다.
          </p>
        </div>
      </div>
    </Card>
  );
}
