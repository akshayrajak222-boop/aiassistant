"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Sparkles, Mic, Volume2, Cpu, Eye, Radio, Zap } from "lucide-react";
import { VoiceState } from "@/hooks/useVoice";

interface AxyFaceProps {
  state: VoiceState;
  onClick: () => void;
  disabled?: boolean;
}

export const AxyFace: React.FC<AxyFaceProps> = ({ state, onClick, disabled }) => {
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";
  const isProcessing = state === "processing";
  const isError = state === "error";

  // Mouse parallax 3D tilt coordinates
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Dynamic Lip-Sync Vocal Amplitude (0.0 = closed, 1.0 = wide open)
  const [mouthOpen, setMouthOpen] = useState(0);

  // Speech rhythm animation loop
  useEffect(() => {
    let animId: number;
    let lastTime = performance.now();
    let syllableTimer = 0;
    let targetOpen = 0;

    const updateMouth = (now: number) => {
      const delta = (now - lastTime) / 1000;
      lastTime = now;

      if (isSpeaking) {
        syllableTimer += delta;
        // Natural speech syllable cadence: changes target phoneme shape every 70-130ms
        if (syllableTimer > 0.09) {
          syllableTimer = 0;
          // Randomize between open vowel, semi-closed consonant, and brief pause
          const rand = Math.random();
          if (rand > 0.85) {
            targetOpen = 0.1; // brief consonant closure (p, b, m)
          } else if (rand > 0.45) {
            targetOpen = 0.6 + Math.random() * 0.4; // open vowel (a, o, u)
          } else {
            targetOpen = 0.3 + Math.random() * 0.3; // semi-open (e, i, s)
          }
        }
        // Smoothly interpolate mouth opening towards target
        setMouthOpen((prev) => prev + (targetOpen - prev) * Math.min(1, delta * 24));
      } else if (isListening) {
        // Subtle rhythmic micro-flutter when listening to incoming sound
        const pulse = 0.05 + Math.sin(now / 150) * 0.05;
        setMouthOpen(pulse);
      } else {
        // Smoothly close lips when idle
        setMouthOpen((prev) => Math.max(0, prev - delta * 8));
      }

      animId = requestAnimationFrame(updateMouth);
    };

    animId = requestAnimationFrame(updateMouth);
    return () => cancelAnimationFrame(animId);
  }, [isSpeaking, isListening]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 18; // -9 to +9 deg
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * -18; // -9 to +9 deg
    setTilt({ x, y });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  // State theme colors
  const stateGlow = isListening
    ? "rgba(244, 63, 94, 0.4)"
    : isSpeaking
    ? "rgba(16, 185, 129, 0.45)"
    : isProcessing
    ? "rgba(245, 158, 11, 0.45)"
    : isError
    ? "rgba(239, 68, 68, 0.5)"
    : "rgba(34, 211, 238, 0.35)";

  const ringColor = isListening
    ? "border-rose-500/60 shadow-[0_0_20px_rgba(244,63,94,0.4)]"
    : isSpeaking
    ? "border-emerald-400/70 shadow-[0_0_25px_rgba(16,185,129,0.5)]"
    : isProcessing
    ? "border-amber-400/60 shadow-[0_0_20px_rgba(245,158,11,0.4)]"
    : "border-cyan-400/50 shadow-[0_0_25px_rgba(34,211,238,0.4)]";

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative flex flex-col items-center justify-center select-none py-2 perspective-1000"
      style={{ perspective: "1200px" }}
    >
      {/* 3D Holographic Canvas Stage */}
      <div
        className="relative w-80 h-96 md:w-96 md:h-[430px] flex items-center justify-center transition-transform duration-200 ease-out cursor-pointer group"
        onClick={onClick}
        title={isListening ? "Stop listening" : isSpeaking ? "Interrupt Axy" : "Click hologram to speak"}
        style={{
          transform: `rotateY(${tilt.x}deg) rotateX(${tilt.y}deg)`,
          transformStyle: "preserve-3d",
        }}
      >
        {/* Ambient Holographic Backlight Aura */}
        <div
          className="absolute inset-x-8 top-12 bottom-12 rounded-full blur-3xl transition-all duration-700 pointer-events-none"
          style={{
            background: stateGlow,
            transform: isSpeaking ? "scale(1.15)" : isListening ? "scale(1.1)" : "scale(0.95)",
          }}
        />

        {/* Orbiting Concentric 3D HUD Rings Around Head */}
        <div
          className={`absolute top-4 w-72 h-72 md:w-80 md:h-80 rounded-full border border-dashed ${ringColor} animate-spin-cw pointer-events-none transition-colors duration-500`}
          style={{
            animationDuration: isProcessing ? "6s" : "28s",
            transform: "rotateX(72deg) scale(0.95)",
          }}
        >
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-cyan-300 shadow-[0_0_12px_#22d3ee]"></div>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_12px_#38bdf8]"></div>
        </div>

        {/* Torso Level 3D Orbiting Ring */}
        <div
          className={`absolute bottom-14 w-84 h-84 md:w-96 md:h-96 rounded-full border-2 border-dotted border-cyan-500/30 animate-spin-ccw pointer-events-none transition-colors duration-500`}
          style={{
            animationDuration: isProcessing ? "5s" : "22s",
            transform: "rotateX(78deg) scale(1.05)",
          }}
        />

        {/* Main Holographic Avatar Container */}
        <div
          className="relative z-10 w-72 h-88 md:w-84 md:h-[390px] rounded-3xl overflow-hidden shadow-2xl border border-cyan-500/30 backdrop-blur-sm bg-slate-950/80 flex items-center justify-center hologram-float"
          style={{
            boxShadow: `0 0 40px ${stateGlow}, inset 0 0 25px rgba(6,182,212,0.15)`,
          }}
        >
          {/* Hologram Base Image */}
          <div className="relative w-full h-full">
            <Image
              src="/axy-hologram.jpg"
              alt="Axy 3D Hologram AI"
              fill
              priority
              className={`object-cover object-center transition-all duration-500 ${
                isSpeaking
                  ? "scale-103 brightness-110 drop-shadow-[0_0_20px_rgba(52,211,153,0.3)]"
                  : isListening
                  ? "scale-102 brightness-105"
                  : isProcessing
                  ? "brightness-110 animate-pulse"
                  : "scale-100 group-hover:scale-102"
              }`}
            />

            {/* Dynamic Mouth / Lip-Sync Overlay */}
            {/* Exactly positioned over the hologram face lips */}
            <div
              className="absolute pointer-events-none z-30 transition-transform duration-75"
              style={{
                top: "41.6%",
                left: "43.8%",
                width: "9.2%",
                height: "3.6%",
                transform: `translate(-50%, -50%) scale(${1 + mouthOpen * 0.15})`,
              }}
            >
              {/* Mouth Cavity Depth Glow when speaking */}
              <div
                className="w-full rounded-full transition-all duration-75 flex items-center justify-center overflow-hidden"
                style={{
                  height: `${Math.max(2, mouthOpen * 11)}px`,
                  backgroundColor: mouthOpen > 0.08 ? "rgba(2, 6, 23, 0.95)" : "transparent",
                  boxShadow:
                    mouthOpen > 0.15
                      ? "0 0 8px rgba(34, 211, 238, 0.8), inset 0 0 6px rgba(56, 189, 248, 0.9)"
                      : "none",
                  border:
                    mouthOpen > 0.12
                      ? "1px solid rgba(103, 232, 249, 0.9)"
                      : "1px solid transparent",
                }}
              >
                {/* Acoustic Energy Core in Mouth */}
                {mouthOpen > 0.2 && (
                  <div
                    className="w-3/4 rounded-full bg-cyan-200 blur-[1px] animate-pulse"
                    style={{
                      height: `${Math.max(1, mouthOpen * 3.5)}px`,
                      boxShadow: "0 0 10px #22d3ee, 0 0 4px #fff",
                    }}
                  />
                )}
              </div>

              {/* Holographic Vocal Wave Ripples radiating from lips when speaking */}
              {isSpeaking && mouthOpen > 0.25 && (
                <div
                  className="absolute -inset-2 rounded-full border border-cyan-400/60 pointer-events-none"
                  style={{
                    animation: "vocal-ripple 0.8s ease-out infinite",
                  }}
                />
              )}
            </div>

            {/* Subtle Chin/Jaw Flex Movement in sync with speech */}
            <div
              className="absolute pointer-events-none z-20"
              style={{
                top: "43.5%",
                left: "43.8%",
                width: "12%",
                height: "4%",
                transform: `translate(-50%, 0) translateY(${mouthOpen * 2.5}px)`,
                background:
                  mouthOpen > 0.2
                    ? "radial-gradient(ellipse at center, rgba(34, 211, 238, 0.25) 0%, transparent 70%)"
                    : "transparent",
              }}
            />

            {/* Glowing Holographic Eyes Layer */}
            <div
              className={`absolute pointer-events-none z-20 transition-all duration-300 blur-[1px] rounded-full ${
                isSpeaking
                  ? "bg-emerald-400/40 shadow-[0_0_15px_#34d399]"
                  : isListening
                  ? "bg-rose-400/45 shadow-[0_0_16px_#fb7185]"
                  : isProcessing
                  ? "bg-amber-300/50 shadow-[0_0_16px_#fbbf24] animate-pulse"
                  : "bg-cyan-300/30 shadow-[0_0_12px_#22d3ee]"
              }`}
              style={{
                top: "28.5%",
                left: "38.5%",
                width: "12%",
                height: "2.8%",
              }}
            />

            {/* Holographic Scanlines Texture Overlay */}
            <div
              className="absolute inset-0 pointer-events-none opacity-25 mix-blend-screen"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(0deg, rgba(34, 211, 238, 0.18), rgba(34, 211, 238, 0.18) 1px, transparent 1px, transparent 3px)",
              }}
            />

            {/* Continuous Hologram Laser Scanline Sweeper */}
            <div
              className="absolute inset-x-0 h-16 pointer-events-none bg-gradient-to-b from-transparent via-cyan-400/25 to-transparent"
              style={{
                animation: isListening
                  ? "hologram-scan 2s ease-in-out infinite"
                  : isProcessing
                  ? "hologram-scan 1.2s linear infinite"
                  : "hologram-scan 4s ease-in-out infinite",
              }}
            />

            {/* Holographic Chromatic Glitch Edge Lines */}
            <div className="absolute inset-0 rounded-3xl border border-cyan-400/20 pointer-events-none" />

            {/* Hologram Projector Beam at Bottom */}
            <div
              className="absolute bottom-0 inset-x-0 h-12 bg-gradient-to-t from-cyan-500/25 to-transparent pointer-events-none"
              style={{
                boxShadow: "inset 0 -10px 20px rgba(6, 182, 212, 0.35)",
              }}
            />
          </div>
        </div>

        {/* High-Tech Hologram Status Badge */}
        <div className="absolute -bottom-4 z-30 px-4 py-1.5 rounded-full bg-slate-900/95 border border-slate-700/80 backdrop-blur-md shadow-2xl flex items-center gap-2 text-xs font-mono tracking-wider">
          {isSpeaking ? (
            <>
              <Volume2 className="w-4 h-4 text-emerald-400 animate-pulse" />
              <span className="text-emerald-300 font-semibold">AXY SPEAKING</span>
            </>
          ) : isListening ? (
            <>
              <Mic className="w-4 h-4 text-rose-400 animate-bounce" />
              <span className="text-rose-300 font-semibold">LISTENING...</span>
            </>
          ) : isProcessing ? (
            <>
              <Cpu className="w-4 h-4 text-amber-400 animate-spin" />
              <span className="text-amber-300 font-semibold">PROCESSING</span>
            </>
          ) : (
            <>
              <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
              <span className="text-cyan-300 font-medium">HOLOGRAM ONLINE</span>
            </>
          )}
        </div>
      </div>

      {/* Helper text under hologram */}
      <p className="mt-6 text-xs text-slate-400 font-mono tracking-wide">
        {isListening
          ? "Listening to your voice... (click hologram to finish)"
          : isSpeaking
          ? "Speaking and animating lips... (click to interrupt)"
          : isProcessing
          ? "Axy is analyzing your input..."
          : "Click 3D Hologram to Speak"}
      </p>

      {/* Hologram Keyframe Animations */}
      <style jsx>{`
        .hologram-float {
          animation: float-bob 6s ease-in-out infinite;
        }

        @keyframes float-bob {
          0%, 100% {
            transform: translateY(0px);
          }
          50% {
            transform: translateY(-8px);
          }
        }

        @keyframes hologram-scan {
          0% {
            top: 2%;
            opacity: 0.15;
          }
          50% {
            top: 88%;
            opacity: 0.6;
          }
          100% {
            top: 2%;
            opacity: 0.15;
          }
        }

        @keyframes vocal-ripple {
          0% {
            transform: scale(0.8);
            opacity: 0.9;
          }
          100% {
            transform: scale(2.2);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
};
