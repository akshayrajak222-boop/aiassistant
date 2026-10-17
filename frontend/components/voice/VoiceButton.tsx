"use client";

import React from "react";
import { Mic, MicOff, Volume2, Loader2, AlertCircle } from "lucide-react";
import { VoiceState } from "@/hooks/useVoice";

interface VoiceButtonProps {
  state: VoiceState;
  onClick: () => void;
  disabled?: boolean;
}

export const VoiceButton: React.FC<VoiceButtonProps> = ({ state, onClick, disabled }) => {
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";
  const isProcessing = state === "processing";
  const isError = state === "error";

  return (
    <div className="relative flex flex-col items-center gap-3">
      {/* Outer Pulse Rings when Listening */}
      {isListening && (
        <>
          <div className="absolute inset-0 rounded-full bg-blue-500/20 animate-ping -z-10 scale-150"></div>
          <div className="absolute inset-0 rounded-full bg-blue-500/30 animate-pulse-ring -z-10 scale-125"></div>
        </>
      )}

      {/* Button */}
      <button
        onClick={onClick}
        disabled={disabled}
        className={`w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl focus:outline-none focus:ring-4 focus:ring-offset-4 focus:ring-offset-slate-950 ${
          isListening
            ? "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/40 focus:ring-rose-500"
            : isSpeaking
            ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/40 focus:ring-emerald-500 animate-pulse"
            : isProcessing
            ? "bg-amber-600 text-white shadow-amber-900/40"
            : isError
            ? "bg-rose-900 text-rose-200 border border-rose-700"
            : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/40 focus:ring-blue-500"
        }`}
      >
        {isListening ? (
          <MicOff className="w-10 h-10" />
        ) : isSpeaking ? (
          <Volume2 className="w-10 h-10" />
        ) : isProcessing ? (
          <Loader2 className="w-10 h-10 animate-spin" />
        ) : isError ? (
          <AlertCircle className="w-10 h-10" />
        ) : (
          <Mic className="w-10 h-10" />
        )}
      </button>

      {/* State Label */}
      <div className="flex flex-col items-center">
        <span className="text-sm font-semibold tracking-wide uppercase text-slate-300">
          {isListening
            ? "Listening..."
            : isSpeaking
            ? "Assistant Speaking..."
            : isProcessing
            ? "Processing..."
            : isError
            ? "Microphone Error"
            : "Push to Speak"}
        </span>
        <span className="text-xs text-slate-500 mt-0.5">
          {isListening
            ? "Click to stop recording"
            : isSpeaking
            ? "Click to interrupt"
            : "Click to start voice conversation"}
        </span>
      </div>
    </div>
  );
};
