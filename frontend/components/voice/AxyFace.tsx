"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Sparkles, Mic, Volume2, Cpu, Eye, Radio } from "lucide-react";
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

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 20; // -10 to +10 deg
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * -20; // -10 to +10 deg
    setTilt({ x, y });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  // State colors
  const glowColor = isListening
    ? "rgba(244, 63, 94, 0.45)"
    : isSpeaking
    ? "rgba(16, 185, 129, 0.55)"
    : isProcessing
    ? "rgba(245, 158, 11, 0.5)"
    : isError
    ? "rgba(239, 68, 68, 0.6)"
    : "rgba(6, 182, 212, 0.45)";

  const ringColor = isListening
    ? "border-rose-500/60 shadow-[0_0_20px_rgba(244,63,94,0.4)]"
    : isSpeaking
    ? "border-emerald-400/70 shadow-[0_0_25px_rgba(16,185,129,0.5)]"
    : isProcessing
    ? "border-amber-400/60 shadow-[0_0_20px_rgba(245,158,11,0.4)]"
    : "border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.35)]";

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative flex flex-col items-center justify-center select-none py-2 perspective-1000"
      style={{ perspective: "1000px" }}
    >
      {/* 3D Holographic Container */}
      <div
        className="relative w-72 h-72 md:w-84 md:h-84 flex items-center justify-center transition-transform duration-200 ease-out cursor-pointer group"
        onClick={onClick}
        title={isListening ? "Stop listening" : isSpeaking ? "Interrupt" : "Click to speak"}
        style={{
          transform: `rotateY(${tilt.x}deg) rotateX(${tilt.y}deg)`,
          transformStyle: "preserve-3d",
        }}
      >
        {/* Ambient Back Glow */}
        <div
          className="absolute inset-0 rounded-full blur-3xl transition-all duration-700 pointer-events-none"
          style={{
            background: glowColor,
            transform: isSpeaking || isListening ? "scale(1.2)" : "scale(0.95)",
          }}
        />

        {/* Concentric Rotating Tech Rings */}
        <div
          className={`absolute w-76 h-76 md:w-88 md:h-88 rounded-full border border-dashed ${ringColor} animate-spin-cw pointer-events-none transition-colors duration-500`}
          style={{ animationDuration: isProcessing ? "8s" : "30s" }}
        >
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_10px_#22d3ee]"></div>
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_10px_#3b82f6]"></div>
        </div>

        <div
          className={`absolute w-68 h-68 md:w-80 md:h-80 rounded-full border-2 border-t-transparent border-b-transparent ${ringColor} animate-spin-ccw pointer-events-none transition-colors duration-500 opacity-60`}
          style={{ animationDuration: isProcessing ? "5s" : "20s" }}
        />

        {/* 3D Avatar Avatar Face Head */}
        <div
          className="relative z-10 w-56 h-56 md:w-64 md:h-64 rounded-full overflow-hidden border-2 border-slate-700/60 shadow-2xl backdrop-blur-md bg-slate-950 flex items-center justify-center"
          style={{
            boxShadow: `0 0 35px ${glowColor}, inset 0 0 20px rgba(0,0,0,0.8)`,
          }}
        >
          {/* Avatar Image */}
          <Image
            src="/axy-avatar.png"
            alt="Axy AI 3D Face"
            width={320}
            height={320}
            priority
            className={`w-full h-full object-cover transition-transform duration-500 ${
              isSpeaking
                ? "scale-105"
                : isListening
                ? "scale-102"
                : "scale-100 group-hover:scale-105"
            }`}
          />

          {/* Holographic Scanline Layer */}
          <div
            className="absolute inset-0 pointer-events-none opacity-30 mix-blend-screen"
            style={{
              backgroundImage:
                "repeating-linear-gradient(0deg, rgba(34, 211, 238, 0.15), rgba(34, 211, 238, 0.15) 1px, transparent 1px, transparent 3px)",
            }}
          />

          {/* Vertical Radar / Laser Face Scanner Sweep */}
          <div
            className="absolute inset-x-0 h-10 pointer-events-none bg-gradient-to-b from-transparent via-cyan-400/30 to-transparent"
            style={{
              animation: isListening
                ? "scanline 2s ease-in-out infinite"
                : isProcessing
                ? "scanline 1s linear infinite"
                : "scanline 4s ease-in-out infinite",
            }}
          />

          {/* Animated Eye Visor Glow Overlay */}
          <div
            className={`absolute top-[38%] left-[26%] right-[26%] h-[8%] rounded-full pointer-events-none transition-all duration-300 blur-[2px] ${
              isSpeaking
                ? "bg-emerald-400/50 shadow-[0_0_15px_#34d399]"
                : isListening
                ? "bg-rose-400/50 shadow-[0_0_15px_#fb7185]"
                : isProcessing
                ? "bg-amber-400/60 shadow-[0_0_15px_#fbbf24] animate-pulse"
                : "bg-cyan-400/40 shadow-[0_0_12px_#22d3ee]"
            }`}
          />

          {/* Speech Audio Visualizer Overlay on Mouth / Jaw Region */}
          <div className="absolute bottom-[24%] left-1/2 -translate-x-1/2 flex items-center justify-center gap-1 z-20 pointer-events-none">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className={`w-1 rounded-full transition-all duration-150 ${
                  isSpeaking
                    ? "bg-emerald-300 shadow-[0_0_8px_#34d399]"
                    : isListening
                    ? "bg-rose-400/80 shadow-[0_0_8px_#fb7185]"
                    : isProcessing
                    ? "bg-amber-400/60"
                    : "bg-cyan-400/40"
                }`}
                style={{
                  height: isSpeaking
                    ? `${8 + Math.abs(Math.sin(Date.now() / 200 + i)) * 18}px`
                    : isListening
                    ? `${4 + (i % 3) * 3}px`
                    : "3px",
                  animation: isSpeaking ? `pulse 0.4s ease-in-out infinite ${i * 0.08}s` : "none",
                }}
              />
            ))}
          </div>

          {/* Center Hologram Vignette */}
          <div className="absolute inset-0 rounded-full border border-cyan-400/20 pointer-events-none" />
        </div>

        {/* Floating Mini Badge Indicator */}
        <div className="absolute -bottom-3 z-30 px-3.5 py-1 rounded-full bg-slate-900/90 border border-slate-700/80 backdrop-blur-md shadow-xl flex items-center gap-1.5 text-[11px] font-mono tracking-wider">
          {isSpeaking ? (
            <>
              <Volume2 className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
              <span className="text-emerald-300 font-semibold">SPEAKING</span>
            </>
          ) : isListening ? (
            <>
              <Mic className="w-3.5 h-3.5 text-rose-400 animate-bounce" />
              <span className="text-rose-300 font-semibold">LISTENING</span>
            </>
          ) : isProcessing ? (
            <>
              <Cpu className="w-3.5 h-3.5 text-amber-400 animate-spin" />
              <span className="text-amber-300 font-semibold">THINKING</span>
            </>
          ) : (
            <>
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-cyan-300">AXY ONLINE</span>
            </>
          )}
        </div>
      </div>

      {/* Subtext info */}
      <p className="mt-5 text-xs text-slate-400 font-mono tracking-wide">
        {isListening
          ? "Listening to your voice... (click face to finish)"
          : isSpeaking
          ? "Speaking... (click face to interrupt)"
          : isProcessing
          ? "Axy is formulating a response..."
          : "Click 3D Face to Speak"}
      </p>

      {/* CSS Keyframe for Laser Scanline */}
      <style jsx>{`
        @keyframes scanline {
          0% {
            top: 5%;
            opacity: 0.2;
          }
          50% {
            top: 85%;
            opacity: 0.6;
          }
          100% {
            top: 5%;
            opacity: 0.2;
          }
        }
      `}</style>
    </div>
  );
};
