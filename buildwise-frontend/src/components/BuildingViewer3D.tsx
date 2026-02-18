import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Environment, Grid, Line } from "@react-three/drei";
import * as THREE from "three";

export interface BuildingViewerProps {
  geometry: {
    total_floor_area_m2?: number;
    num_floors_above?: number;
    floor_to_floor_height_m?: number;
    aspect_ratio?: number;
    wwr?: number;
    orientation_deg?: number;
  };
  buildingType?: string;
}

const TYPE_COLORS: Record<string, string> = {
  large_office: "#3B82F6",
  medium_office: "#6366F1",
  small_office: "#8B5CF6",
  standalone_retail: "#F59E0B",
  primary_school: "#10B981",
  hospital: "#EF4444",
};

function Building({ geometry, buildingType }: BuildingViewerProps) {
  const floors = geometry.num_floors_above ?? 3;
  const floorHeight = geometry.floor_to_floor_height_m ?? 3.5;
  const totalArea = geometry.total_floor_area_m2 ?? 4000;
  const aspectRatio = geometry.aspect_ratio ?? 1.5;
  const wwr = geometry.wwr ?? 0.4;
  const orientDeg = geometry.orientation_deg ?? 0;

  const dims = useMemo(() => {
    const footprint = totalArea / floors;
    const width = Math.sqrt(footprint / aspectRatio);
    const depth = width * aspectRatio;
    const height = floors * floorHeight;
    const maxDim = Math.max(width, depth, height);
    const scale = maxDim > 0 ? 8 / maxDim : 1;
    return {
      w: width * scale,
      d: depth * scale,
      h: height * scale,
      floorH: floorHeight * scale,
      floors,
      wwr,
    };
  }, [totalArea, floors, floorHeight, aspectRatio, wwr]);

  const color = TYPE_COLORS[buildingType ?? ""] ?? "#94A3B8";

  const windows = useMemo(() => {
    const result: { pos: [number, number, number]; size: [number, number]; rotation: [number, number, number] }[] = [];
    const { w, d, floorH, floors: fl, wwr: windowRatio } = dims;
    const h = dims.h;
    const windowH = floorH * 0.55;
    const windowOffsetY = floorH * 0.3;

    for (let f = 0; f < fl; f++) {
      const floorY = -h / 2 + f * floorH + windowOffsetY;
      const frontW = w * windowRatio * 0.9;
      const sideW = d * windowRatio * 0.9;

      result.push(
        { pos: [0, floorY, d / 2 + 0.01], size: [frontW, windowH], rotation: [0, 0, 0] },
        { pos: [0, floorY, -d / 2 - 0.01], size: [frontW, windowH], rotation: [0, Math.PI, 0] },
        { pos: [w / 2 + 0.01, floorY, 0], size: [sideW, windowH], rotation: [0, Math.PI / 2, 0] },
        { pos: [-w / 2 - 0.01, floorY, 0], size: [sideW, windowH], rotation: [0, -Math.PI / 2, 0] },
      );
    }
    return result;
  }, [dims]);

  const floorLines = useMemo(() => {
    const lines: [number, number, number][][] = [];
    const { w, d, h, floorH, floors: fl } = dims;
    for (let f = 1; f < fl; f++) {
      const y = -h / 2 + f * floorH;
      const hw = w / 2;
      const hd = d / 2;
      lines.push([
        [-hw, y, hd], [hw, y, hd], [hw, y, -hd], [-hw, y, -hd], [-hw, y, hd],
      ]);
    }
    return lines;
  }, [dims]);

  const rotRad = (orientDeg * Math.PI) / 180;

  return (
    <group rotation={[0, rotRad, 0]}>
      {/* Main body */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[dims.w, dims.h, dims.d]} />
        <meshStandardMaterial color={color} transparent opacity={0.85} />
      </mesh>

      {/* Wireframe overlay */}
      <mesh>
        <boxGeometry args={[dims.w, dims.h, dims.d]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.3} />
      </mesh>

      {/* Windows */}
      {windows.map((win, i) => (
        <mesh key={i} position={win.pos} rotation={win.rotation}>
          <planeGeometry args={win.size} />
          <meshStandardMaterial
            color="#87CEEB"
            transparent
            opacity={0.6}
            side={THREE.DoubleSide}
            metalness={0.8}
            roughness={0.1}
          />
        </mesh>
      ))}

      {/* Floor separator lines */}
      {floorLines.map((pts, i) => (
        <Line key={i} points={pts} color="#ffffff" lineWidth={1} transparent opacity={0.5} />
      ))}

      {/* Roof */}
      <mesh position={[0, dims.h / 2 + 0.02, 0]}>
        <boxGeometry args={[dims.w + 0.1, 0.04, dims.d + 0.1]} />
        <meshStandardMaterial color="#374151" />
      </mesh>

      {/* Ground base */}
      <mesh position={[0, -dims.h / 2 - 0.02, 0]}>
        <boxGeometry args={[dims.w + 0.15, 0.04, dims.d + 0.15]} />
        <meshStandardMaterial color="#6B7280" />
      </mesh>
    </group>
  );
}

export default function BuildingViewer3D({ geometry, buildingType }: BuildingViewerProps) {
  const floors = geometry.num_floors_above ?? 3;
  const camDist = floors > 10 ? 18 : floors > 5 ? 14 : 12;

  return (
    <div className="h-full w-full min-h-[300px] rounded-lg overflow-hidden bg-gradient-to-b from-sky-100 to-sky-50">
      <Canvas
        camera={{ position: [camDist, camDist * 0.6, camDist], fov: 35 }}
        shadows
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 15, 10]} intensity={1} castShadow />
        <directionalLight position={[-5, 8, -5]} intensity={0.3} />

        <Building geometry={geometry} buildingType={buildingType} />

        <Grid
          args={[30, 30]}
          position={[0, -4.5, 0]}
          cellSize={1}
          cellColor="#d1d5db"
          sectionSize={5}
          sectionColor="#9ca3af"
          fadeDistance={25}
          infiniteGrid
        />

        <OrbitControls
          makeDefault
          enablePan={false}
          minDistance={5}
          maxDistance={30}
          maxPolarAngle={Math.PI / 2.1}
          autoRotate
          autoRotateSpeed={0.5}
        />
        <Environment preset="city" />
      </Canvas>
    </div>
  );
}
