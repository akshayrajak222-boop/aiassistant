"use client";

import React, { useMemo } from "react";
import { Mic, MicOff, Volume2, Cpu, Sparkles, Radio } from "lucide-react";
import { VoiceState } from "@/hooks/useVoice";

interface JarvisOrbProps {
  state: VoiceState;
  onClick: () => void;
  disabled?: boolean;
}

export const JarvisOrb: React.FC<JarvisOrbProps> = ({ state, onClick, disabled }) => {
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";
  const isProcessing = state === "processing";
  const isError = state === "error";

  // Pre-generate pseudo-random animation delays and heights for 24 audio wave bars
  const waveBars = useMemo(() => {
    return Array.from({ length: 24 }).map((_, i) => ({
      delay: `${(i * 0.05).toFixed(2)}s`,
      duration: `${(0.4 + (i % 5) * 0.15).toFixed(2)}s`,
      defaultHeight: `${12 + (Math.sin(i) * 10 + 10)}px`,
      maxScale: isSpeaking || isListening ? 1.5 + (i % 4) * 0.4 : 0.3,
    }));
  }, [isSpeaking, isListening]);

  // Color schemes based on state
  const stateColor = isListening
    ? "from-rose-500 via-red-500 to-rose-700 shadow-rose-500/50 text-rose-400"
    : isSpeaking
    ? "from-emerald-400 via-teal-500 to-emerald-600 shadow-emerald-500/50 text-emerald-400"
    : isProcessing
    ? "from-amber-400 via-yellow-500 to-amber-600 shadow-amber-500/50 text-amber-400"
    : isError
    ? "from-red-600 via-rose-700 to-red-900 shadow-red-500/50 text-rose-400"
    : "from-cyan-400 via-blue-500 to-indigo-600 shadow-cyan-500/50 text-cyan-400";

  const ringColor = isListening
    ? "border-rose-500/50"
    : isSpeaking
    ? "border-emerald-500/50"
    : isProcessing
    ? "border-amber-500/50"
    : "border-cyan-500/40";

  return (
    <div className="relative flex flex-col items-center justify-center select-none py-4">
      {/* Container with fixed dimension for perfect concentric centering */}
      <div className="relative w-80 h-80 flex items-center justify-center">
        {/* Outermost Pulsing Ambient Aura */}
        <div
          className={`absolute inset-0 rounded-full bg-gradient-to-tr ${stateColor} opacity-20 blur-3xl transition-all duration-700 ${
            isListening || isSpeaking ? "scale-125 opacity-40" : "scale-100 opacity-15"
          }`}
        />

        {/* Outer Ring 1: Technical Compass Ticks (Rotates Clockwise) */}
        <div
          className={`absolute w-72 h-72 rounded-full border border-dashed ${ringColor} animate-spin-cw opacity-60 pointer-events-none transition-colors duration-500`}
          style={{ animationDuration: isProcessing ? "6s" : "32s" }}
        >
          {/* Accent Markers */}
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]"></div>
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]"></div>
          <div className="absolute top-1/2 -left-1 -translate-y-1/2 w-2 h-2 rounded-full bg-indigo-400"></div>
          <div className="absolute top-1/2 -right-1 -translate-y-1/2 w-2 h-2 rounded-full bg-cyan-400"></div>
        </div>

        {/* Middle Ring 2: Segmented Arc HUD (Rotates Counter-Clockwise) */}
        <div
          className={`absolute w-60 h-60 rounded-full border-2 border-t-transparent border-b-transparent ${ringColor} animate-spin-ccw opacity-75 pointer-events-none transition-colors duration-500`}
          style={{ animationDuration: isProcessing ? "4s" : "20s" }}
        />

        {/* Inner Ring 3: Fast Gyro Ring (Only when Active / Processing) */}
        <div
          className={`absolute w-48 h-48 rounded-full border border-dotted ${ringColor} animate-spin-cw opacity-50 pointer-events-none transition-all duration-500 ${
            isProcessing ? "scale-110 opacity-90 animate-spin-cw-fast" : "scale-100 opacity-40"
          }`}
        />

        {/* Radar Scanner Sweep Line */}
        <div
          className="absolute w-56 h-56 rounded-full pointer-events-none opacity-40 animate-spin-cw"
          style={{
            background:
              "conic-gradient(from 0deg, transparent 0deg, transparent 300deg, rgba(34, 211, 238, 0.4) 360deg)",
            animationDuration: isListening ? "2.5s" : "5s",
          }}
        />

        {/* Center Holographic Core Orb (Interactive Button) */}
        <button
          onClick={onClick}
          disabled={disabled}
          title={isListening ? "Stop listening" : isSpeaking ? "Interrupt" : "Click to speak"}
          className={`relative z-20 w-36 h-36 rounded-full flex flex-col items-center justify-center p-2 bg-gradient-to-tr ${stateColor} shadow-2xl transition-all duration-500 transform hover:scale-105 active:scale-95 focus:outline-none focus:ring-4 focus:ring-cyan-500/50 cursor-pointer group`}
        >
          {/* Glass Inner Reflection Layer */}
          <div className="absolute inset-1 rounded-full bg-slate-950/70 backdrop-blur-md border border-white/20 flex flex-col items-center justify-center overflow-hidden">
            {/* Holographic light shimmer */}
            <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-black/40 pointer-events-none" />

            {/* Core Center Icon */}
            <div className="relative z-10 flex flex-col items-center justify-center transition-transform duration-300 group-hover:scale-110">
              {isListening ? (
                <div className="flex flex-col items-center gap-1">
                  <MicOff className="w-10 h-10 text-rose-400 animate-pulse" />
                  <span className="text-[10px] font-mono tracking-widest text-rose-300 uppercase font-semibold">
                    REC
                  </span>
                </div>
              ) : isSpeaking ? (
                <div className="flex flex-col items-center gap-1">
                  <Volume2 className="w-10 h-10 text-emerald-400 animate-bounce" />
                  <span className="text-[10px] font-mono tracking-widest text-emerald-300 uppercase font-semibold">
                    VOX
                  </span>
                </div>
              ) : isProcessing ? (
                <div className="flex flex-col items-center gap-1">
                  <Cpu className="w-10 h-10 text-amber-400 animate-spin" />
                  <span className="text-[10px] font-mono tracking-widest text-amber-300 uppercase font-semibold">
                    THINK
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-1">
                  <Sparkles className="w-10 h-10 text-cyan-400 transition-all duration-300 group-hover:text-cyan-300 animate-pulse" />
                  <span className="text-[10px] font-mono tracking-widest text-cyan-300 uppercase font-semibold">
                    JARVIS
                  </span>
                </div>
              )}
            </div>

            {/* Subtle internal ring */}
            <div className="absolute w-24 h-24 rounded-full border border-cyan-400/20 pointer-events-none" />
          </div>
        </button>
      </div>

      {/* Dynamic 24-Bar Sound Frequency Visualizer */}
      <div className="flex items-center justify-center gap-1.5 h-12 px-6 my-2">
        {waveBars.map((bar, i) => (
          <div
            key={i}
            className={`w-1 rounded-full transition-all duration-300 ${
              isListening
                ? "bg-rose-500 shadow-[0_0_8px_#f43f5e]"
                : isSpeaking
                ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                : isProcessing
                ? "bg-amber-400 shadow-[0_0_8px_#fbbf24]"
                : "bg-cyan-500/40"
            }`}
            style={{
              height: isListening || isSpeaking ? "36px" : isProcessing ? "20px" : "8px",
              animation:
                isListening || isSpeaking || isProcessing
                  ? `wave-bounce ${bar.duration} ease-in-out infinite alternate`
                  : "none",
              animationDelay: bar.delay,
            }}
          />
        ))}
      </div>

      {/* Cyber HUD State Telemetry Indicator */}
      <div className="flex flex-col items-center gap-1 mt-1 z-10">
        <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 px-3.5 py-1.5 rounded-full backdrop-blur-md shadow-lg">
          <span
            className={`w-2 h-2 rounded-full ${
              isListening
                ? "bg-rose-500 animate-ping"
                : isSpeaking
                ? "bg-emerald-400 animate-ping"
                : isProcessing
                ? "bg-amber-400 animate-pulse"
                : "bg-cyan-400 animate-pulse"
            }`}
          />
          <span className="text-xs font-mono tracking-wider uppercase font-semibold text-slate-200">
            {isListening
              ? "AURAL SENSORS ACTIVE"
              : isSpeaking
              ? "SYNTHESIZING VOCAL RESPONSE"
              : isProcessing
              ? "NEURAL COMPUTATION"
              : "JARVIS CORE ONLINE • READY"}
          </span>
        </div>
        <p className="text-[11px] text-slate-500 tracking-wide mt-1">
          {isListening
            ? "Speak now — release or click to submit"
            : isSpeaking
            ? "Click orb to interrupt audio"
            : "Click central core to transmit voice"}
        </p>
      </div>
    </div>
  );
};
