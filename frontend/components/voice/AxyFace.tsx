"use client";

import React, { useEffect, useRef, useState } from "react";
import { Mic, Volume2, Cpu, Radio, Sparkles } from "lucide-react";
import { VoiceState } from "@/hooks/useVoice";

interface AxyFaceProps {
  state: VoiceState;
  onClick: () => void;
  disabled?: boolean;
}

// ── 3D Geometry Utilities ──────────────────────────────────────────────────

interface Mesh3D {
  vertices: [number, number, number][];
  edges: [number, number][];
}

function buildIcosphere(): Mesh3D {
  const phi = (1 + Math.sqrt(5)) / 2;
  const rawVerts: [number, number, number][] = [
    [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
    [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
    [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1],
  ];

  const vertices: [number, number, number][] = rawVerts.map(([x, y, z]) => {
    const l = Math.hypot(x, y, z);
    return [x / l, y / l, z / l];
  });

  let faces: [number, number, number][] = [
    [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
    [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
    [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
    [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
  ];

  const midpointMap = new Map<string, number>();
  function getMidpoint(v1: number, v2: number): number {
    const key = v1 < v2 ? `${v1}_${v2}` : `${v2}_${v1}`;
    if (midpointMap.has(key)) return midpointMap.get(key)!;
    const p1 = vertices[v1];
    const p2 = vertices[v2];
    const mx = (p1[0] + p2[0]) / 2;
    const my = (p1[1] + p2[1]) / 2;
    const mz = (p1[2] + p2[2]) / 2;
    const l = Math.hypot(mx, my, mz);
    const idx = vertices.length;
    vertices.push([mx / l, my / l, mz / l]);
    midpointMap.set(key, idx);
    return idx;
  }

  // 1 subdivision -> 42 vertices, 80 faces, 120 edges
  const newFaces: [number, number, number][] = [];
  for (const [a, b, c] of faces) {
    const ab = getMidpoint(a, b);
    const bc = getMidpoint(b, c);
    const ca = getMidpoint(c, a);
    newFaces.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
  }
  faces = newFaces;

  const edgeSet = new Set<string>();
  const edges: [number, number][] = [];
  for (const [a, b, c] of faces) {
    for (const [u, v] of [
      [a, b],
      [b, c],
      [c, a],
    ]) {
      const key = u < v ? `${u}_${v}` : `${v}_${u}`;
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        edges.push([u, v]);
      }
    }
  }

  return { vertices, edges };
}

interface RaySpike {
  dir: [number, number, number];
  lengthFactor: number;
  phase: number;
  speed: number;
  width: number;
}

function buildRays(count = 32): RaySpike[] {
  const rays: RaySpike[] = [];
  for (let i = 0; i < count; i++) {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / count);
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
    const x = Math.sin(phi) * Math.cos(theta);
    const y = Math.sin(phi) * Math.sin(theta);
    const z = Math.cos(phi);
    rays.push({
      dir: [x, y, z],
      lengthFactor: 1.25 + (i % 5) * 0.18,
      phase: (i * 0.3) % (Math.PI * 2),
      speed: 2 + (i % 3) * 1.5,
      width: 1.4 + (i % 3) * 0.6,
    });
  }
  return rays;
}

interface Particle {
  radius: number;
  theta: number;
  speed: number;
  tilt: number;
  yOffset: number;
  size: number;
  alpha: number;
  twinklePhase: number;
}

function buildParticles(count = 340): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    particles.push({
      radius: 1.22 + Math.random() * 0.65,
      theta: Math.random() * Math.PI * 2,
      speed: 0.006 + Math.random() * 0.012,
      tilt: 0.42 + (Math.random() - 0.5) * 0.22,
      yOffset: (Math.random() - 0.5) * 0.38,
      size: 0.8 + Math.random() * 2.2,
      alpha: 0.35 + Math.random() * 0.65,
      twinklePhase: Math.random() * Math.PI * 2,
    });
  }
  return particles;
}

// ─────────────────────────────────────────────────────────────────────────────

export const AxyFace: React.FC<AxyFaceProps> = ({ state, onClick, disabled }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const isListening = state === "listening";
  const isSpeaking = state === "speaking";
  const isProcessing = state === "processing";
  const isError = state === "error";

  // Mouse Parallax coordinates (smoothly interpolated)
  const targetTilt = useRef({ x: 0, y: 0 });
  const currentTilt = useRef({ x: 0, y: 0 });

  // Real-time speech amplitude modulation
  const speechPulse = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const icosphere = buildIcosphere();
    const rays = buildRays(34);
    const particles = buildParticles(360);

    let animId: number;
    let lastTime = performance.now();
    let rotY = 0;
    let rotX = 0.2;
    let rotZ = 0;
    let speechTimer = 0;
    let targetSpeechVal = 0;

    const render = (now: number) => {
      const delta = Math.min(0.1, (now - lastTime) / 1000);
      lastTime = now;

      // Handle speech rhythm dynamics
      if (isSpeaking) {
        speechTimer += delta;
        if (speechTimer > 0.08) {
          speechTimer = 0;
          targetSpeechVal = 0.3 + Math.random() * 0.7; // energetic vocal pulse
        }
        speechPulse.current += (targetSpeechVal - speechPulse.current) * Math.min(1, delta * 18);
      } else if (isListening) {
        speechPulse.current = 0.15 + Math.sin(now / 180) * 0.08;
      } else {
        speechPulse.current = Math.max(0, speechPulse.current - delta * 4);
      }

      // Smooth mouse parallax interpolation
      currentTilt.current.x += (targetTilt.current.x - currentTilt.current.x) * (delta * 6);
      currentTilt.current.y += (targetTilt.current.y - currentTilt.current.y) * (delta * 6);

      // Continuous 3D Core Rotation
      const spinSpeed = isProcessing ? 1.8 : isSpeaking ? 0.95 : 0.45;
      rotY += delta * spinSpeed;
      rotX = 0.22 + Math.sin(now / 3200) * 0.12 + currentTilt.current.y;
      rotZ = Math.cos(now / 4000) * 0.08;

      const yaw = rotY + currentTilt.current.x;
      const pitch = rotX;
      const roll = rotZ;

      // Trigonometry lookup for frame
      const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
      const cosX = Math.cos(pitch), sinX = Math.sin(pitch);
      const cosZ = Math.cos(roll), sinZ = Math.sin(roll);

      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;
      const baseRadius = width * 0.23;

      // Clear canvas with deep dark transparent backing
      ctx.clearRect(0, 0, width, height);

      // 3D Point Projection Helper
      const project = (x: number, y: number, z: number, scaleFactor = 1) => {
        // Rotate Y (Yaw)
        let x1 = x * cosY + z * sinY;
        let y1 = y;
        let z1 = -x * sinY + z * cosY;

        // Rotate X (Pitch)
        let x2 = x1;
        let y2 = y1 * cosX - z1 * sinX;
        let z2 = y1 * sinX + z1 * cosX;

        // Rotate Z (Roll)
        let x3 = x2 * cosZ - y2 * sinZ;
        let y3 = x2 * sinZ + y2 * cosZ;
        let z3 = z2;

        const fov = 650;
        const pScale = fov / (fov + z3 * baseRadius * scaleFactor);
        const px = cx + x3 * baseRadius * scaleFactor * pScale;
        const py = cy + y3 * baseRadius * scaleFactor * pScale;
        return { px, py, pz: z3, pScale };
      };

      // ── Step 1: Ambient Background Core Aura ──────────────────────────────
      const auraPulse = 1 + speechPulse.current * 0.35;
      const auraGrad = ctx.createRadialGradient(cx, cy, 10, cx, cy, baseRadius * 1.9 * auraPulse);

      if (isListening) {
        auraGrad.addColorStop(0, "rgba(251, 113, 133, 0.4)");
        auraGrad.addColorStop(0.4, "rgba(244, 63, 94, 0.15)");
        auraGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      } else if (isProcessing) {
        auraGrad.addColorStop(0, "rgba(251, 191, 36, 0.45)");
        auraGrad.addColorStop(0.4, "rgba(245, 158, 11, 0.18)");
        auraGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      } else {
        // Warm Fiery Amber / Solar Gold (Matches user reference)
        auraGrad.addColorStop(0, "rgba(255, 185, 40, 0.45)");
        auraGrad.addColorStop(0.35, "rgba(255, 115, 0, 0.2)");
        auraGrad.addColorStop(0.7, "rgba(230, 60, 0, 0.08)");
        auraGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      }
      ctx.fillStyle = auraGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, baseRadius * 1.9 * auraPulse, 0, Math.PI * 2);
      ctx.fill();

      // ── Step 2: Back-hemisphere Particles (z < 0) ─────────────────────────
      particles.forEach((p) => {
        p.theta += p.speed * (isProcessing ? 2.5 : isSpeaking ? 1.6 : 1);
        const px = Math.cos(p.theta) * p.radius;
        const py = Math.sin(p.theta) * p.radius * Math.cos(p.tilt) + p.yOffset;
        const pz = Math.sin(p.theta) * p.radius * Math.sin(p.tilt);

        const proj = project(px, py, pz);
        if (proj.pz < 0) {
          const twinkle = Math.sin(now * 0.003 * p.speed * 100 + p.twinklePhase);
          const alpha = Math.max(0.1, p.alpha * (0.45 + twinkle * 0.25) * 0.6);
          ctx.beginPath();
          ctx.arc(proj.px, proj.py, p.size * proj.pScale * 0.8, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 160, 30, ${alpha})`;
          ctx.fill();
        }
      });

      // ── Step 3: Back-hemisphere Geodesic Sphere Wireframe ─────────────────
      const projectedVerts = icosphere.vertices.map(([vx, vy, vz]) => project(vx, vy, vz));

      ctx.lineWidth = 1.0;
      icosphere.edges.forEach(([v1, v2]) => {
        const p1 = projectedVerts[v1];
        const p2 = projectedVerts[v2];
        // Draw back edges dimmer
        if (p1.pz < 0 || p2.pz < 0) {
          const avgZ = (p1.pz + p2.pz) / 2;
          const alpha = Math.max(0.08, 0.25 + avgZ * 0.2);
          ctx.strokeStyle = `rgba(230, 95, 10, ${alpha})`;
          ctx.beginPath();
          ctx.moveTo(p1.px, p1.py);
          ctx.lineTo(p2.px, p2.py);
          ctx.stroke();
        }
      });

      // ── Step 4: Back Orbital Rings / Ribbon Arcs ──────────────────────────
      const drawRing = (tiltAngle: number, radiusScale: number, arcStart: number, arcEnd: number, isFront: boolean, ringWidth = 3) => {
        const steps = 70;
        const cosT = Math.cos(tiltAngle);
        const sinT = Math.sin(tiltAngle);

        ctx.beginPath();
        let first = true;
        for (let i = 0; i <= steps; i++) {
          const t = arcStart + (i / steps) * (arcEnd - arcStart);
          const rx = Math.cos(t) * radiusScale;
          const ry = Math.sin(t) * radiusScale * cosT;
          const rz = Math.sin(t) * radiusScale * sinT;

          const pt = project(rx, ry, rz);
          const belongsToLayer = isFront ? pt.pz >= 0 : pt.pz < 0;

          if (belongsToLayer) {
            if (first) {
              ctx.moveTo(pt.px, pt.py);
              first = false;
            } else {
              ctx.lineTo(pt.px, pt.py);
            }
          } else {
            first = true;
          }
        }
        ctx.lineWidth = ringWidth;
        ctx.stroke();
      };

      // Draw back portion of orbital ribbon
      ctx.strokeStyle = "rgba(255, 140, 20, 0.3)";
      drawRing(0.55, 1.45, 0, Math.PI * 2, false, 4);
      drawRing(-0.65, 1.35, now * 0.0006, now * 0.0006 + Math.PI * 1.5, false, 2);

      // ── Step 5: High-Energy Radial Needles / Laser Spikes ──────────────────
      rays.forEach((ray) => {
        const flare = 1 + speechPulse.current * 0.55 + Math.sin(now * 0.005 * ray.speed + ray.phase) * 0.15;
        const rayLen = ray.lengthFactor * flare;

        const tip = project(ray.dir[0] * rayLen, ray.dir[1] * rayLen, ray.dir[2] * rayLen);
        const origin = project(ray.dir[0] * 0.15, ray.dir[1] * 0.15, ray.dir[2] * 0.15);

        // Ray stroke with radiant glow gradient
        const rayGrad = ctx.createLinearGradient(origin.px, origin.py, tip.px, tip.py);
        rayGrad.addColorStop(0, "rgba(255, 255, 220, 0.95)");
        rayGrad.addColorStop(0.3, "rgba(255, 195, 45, 0.85)");
        rayGrad.addColorStop(0.7, "rgba(255, 95, 10, 0.5)");
        rayGrad.addColorStop(1, "rgba(255, 50, 0, 0)");

        ctx.strokeStyle = rayGrad;
        ctx.lineWidth = ray.width * tip.pScale;
        ctx.beginPath();
        ctx.moveTo(origin.px, origin.py);
        ctx.lineTo(tip.px, tip.py);
        ctx.stroke();

        // Tip spark
        if (tip.pz > -0.2) {
          ctx.fillStyle = "rgba(255, 240, 160, 0.8)";
          ctx.beginPath();
          ctx.arc(tip.px, tip.py, 1.2 * tip.pScale, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      // ── Step 6: Blazing Central Fusion Star / Nucleus ─────────────────────
      const coreSize = baseRadius * (0.28 + speechPulse.current * 0.12);
      const starGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, coreSize);

      starGrad.addColorStop(0, "#ffffff");
      starGrad.addColorStop(0.2, "#fffb96");
      starGrad.addColorStop(0.5, "#ffaa00");
      starGrad.addColorStop(0.85, "#ff5500");
      starGrad.addColorStop(1, "rgba(255, 60, 0, 0)");

      ctx.fillStyle = starGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, coreSize, 0, Math.PI * 2);
      ctx.fill();

      // Intense White Center Point
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(cx, cy, coreSize * 0.35, 0, Math.PI * 2);
      ctx.fill();

      // ── Step 7: Front-hemisphere Geodesic Sphere Wireframe ────────────────
      ctx.lineWidth = 1.4;
      icosphere.edges.forEach(([v1, v2]) => {
        const p1 = projectedVerts[v1];
        const p2 = projectedVerts[v2];
        if (p1.pz >= 0 && p2.pz >= 0) {
          const avgZ = (p1.pz + p2.pz) / 2;
          const alpha = Math.min(1, 0.5 + avgZ * 0.55);

          // Glowing golden wireframe line
          ctx.strokeStyle = `rgba(255, 215, 80, ${alpha})`;
          ctx.beginPath();
          ctx.moveTo(p1.px, p1.py);
          ctx.lineTo(p2.px, p2.py);
          ctx.stroke();
        }
      });

      // Illuminated Vertex Nodes on Front Sphere
      projectedVerts.forEach((p) => {
        if (p.pz > 0.1) {
          ctx.fillStyle = `rgba(255, 245, 180, ${p.pz * 0.9})`;
          ctx.beginPath();
          ctx.arc(p.px, p.py, 1.6 * p.pScale, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      // ── Step 8: Front Orbital Rings / Wide Golden Ribbon Band ─────────────
      // Main Ribbon Arc (Wide 3D sweeping band, exactly as in user image)
      ctx.strokeStyle = "rgba(255, 175, 45, 0.95)";
      ctx.shadowColor = "rgba(255, 150, 0, 0.8)";
      ctx.shadowBlur = 12;
      drawRing(0.55, 1.45, 0, Math.PI * 2, true, 5.5);

      // Inner Ribbon Arc Highlight
      ctx.strokeStyle = "rgba(255, 240, 160, 0.9)";
      ctx.shadowBlur = 6;
      drawRing(0.55, 1.45, 0, Math.PI * 2, true, 1.8);

      // Counter-rotating Gyro Ribbon
      ctx.shadowBlur = 0;
      ctx.strokeStyle = "rgba(255, 140, 20, 0.85)";
      drawRing(-0.65, 1.35, now * 0.0006, now * 0.0006 + Math.PI * 1.5, true, 3);

      // Equatorial HUD Segmented Arc
      ctx.strokeStyle = "rgba(255, 200, 70, 0.75)";
      drawRing(0.12, 1.65, -now * 0.0008, -now * 0.0008 + Math.PI * 0.85, true, 2);

      // ── Step 9: Front-hemisphere Stardust Ember Particles ─────────────────
      particles.forEach((p) => {
        const px = Math.cos(p.theta) * p.radius;
        const py = Math.sin(p.theta) * p.radius * Math.cos(p.tilt) + p.yOffset;
        const pz = Math.sin(p.theta) * p.radius * Math.sin(p.tilt);

        const proj = project(px, py, pz);
        if (proj.pz >= 0) {
          const twinkle = Math.sin(now * 0.004 * p.speed * 100 + p.twinklePhase);
          const alpha = Math.min(1, p.alpha * (0.7 + twinkle * 0.3) * (0.8 + proj.pz * 0.4));
          const pRadius = p.size * proj.pScale * (1 + speechPulse.current * 0.2);

          // Glowing ember particle
          ctx.beginPath();
          ctx.arc(proj.px, proj.py, pRadius, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 220, 100, ${alpha})`;
          ctx.shadowColor = "rgba(255, 160, 30, 0.9)";
          ctx.shadowBlur = 8;
          ctx.fill();
        }
      });
      ctx.shadowBlur = 0; // Reset shadow

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [isSpeaking, isListening, isProcessing, isError]);

  // Handle Mouse Tilt Inertia
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 0.65;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * -0.65;
    targetTilt.current = { x, y };
  };

  const handleMouseLeave = () => {
    targetTilt.current = { x: 0, y: 0 };
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative flex flex-col items-center justify-center select-none py-2"
    >
      {/* 3D Canvas Stage */}
      <div
        onClick={onClick}
        title={isListening ? "Stop listening" : isSpeaking ? "Interrupt Axy" : "Click 3D Core to speak"}
        className="relative w-80 h-80 sm:w-96 sm:h-96 md:w-[420px] md:h-[420px] flex items-center justify-center cursor-pointer group transition-transform duration-300 hover:scale-[1.02]"
      >
        <canvas
          ref={canvasRef}
          width={840}
          height={840}
          className="w-full h-full drop-shadow-[0_0_50px_rgba(255,140,0,0.35)]"
        />

        {/* High-Tech Status HUD Pill */}
        <div className="absolute -bottom-2 z-30 px-4 py-1.5 rounded-full bg-slate-900/95 border border-amber-500/40 backdrop-blur-md shadow-2xl flex items-center gap-2 text-xs font-mono tracking-wider transition-all duration-300 group-hover:border-amber-400">
          {isSpeaking ? (
            <>
              <Volume2 className="w-4 h-4 text-emerald-400 animate-pulse" />
              <span className="text-emerald-300 font-semibold">AXY TRANSMITTING</span>
            </>
          ) : isListening ? (
            <>
              <Mic className="w-4 h-4 text-rose-400 animate-bounce" />
              <span className="text-rose-300 font-semibold">LISTENING...</span>
            </>
          ) : isProcessing ? (
            <>
              <Cpu className="w-4 h-4 text-amber-400 animate-spin" />
              <span className="text-amber-300 font-semibold">SYNTHESIZING</span>
            </>
          ) : (
            <>
              <Radio className="w-4 h-4 text-amber-400 animate-pulse" />
              <span className="text-amber-300 font-medium">3D QUANTUM CORE // ONLINE</span>
            </>
          )}
        </div>
      </div>

      {/* Guide label */}
      <p className="mt-5 text-xs text-amber-400/80 font-mono tracking-wide">
        {isListening
          ? "Listening to your voice... (click core to finish)"
          : isSpeaking
          ? "Axy is speaking... (click core to interrupt)"
          : isProcessing
          ? "Processing input through neural model..."
          : "Click 3D Core to Speak"}
      </p>
    </div>
  );
};
