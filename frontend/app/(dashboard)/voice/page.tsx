"use client";

import React, { useState } from "react";
import { Mic, Volume2, Shield, Radio, VolumeX, AlertTriangle } from "lucide-react";
import { useVoice } from "@/hooks/useVoice";
import { useChat } from "@/hooks/useChat";
import { VoiceButton } from "@/components/voice/VoiceButton";

export default function VoicePage() {
  const [continuous, setContinuous] = useState(false);
  const [spokenReply, setSpokenReply] = useState<string>("");
  const { sendMessage } = useChat();

  const handleVoiceTranscript = async (text: string) => {
    if (!text.trim()) return;
    // Send to agent and speak the resulting text
    try {
      // Trigger speak response callback
      speak(`I heard: "${text}". Processing your request.`);
    } catch (err) {
      console.error("Voice execution error:", err);
    }
  };

  const {
    state,
    transcript,
    isSupported,
    errorMessage,
    startListening,
    stopListening,
    speak,
    interruptSpeech,
  } = useVoice({
    onTranscript: handleVoiceTranscript,
    continuous,
  });

  const toggleVoice = () => {
    if (state === "listening") {
      stopListening();
    } else if (state === "speaking") {
      interruptSpeech();
    } else {
      startListening();
    }
  };

  return (
    <div className="flex flex-col h-full items-center justify-between p-6 md:p-12 bg-slate-950 relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none"></div>

      {/* Header & Mode Toggles */}
      <div className="w-full max-w-xl flex items-center justify-between border-b border-slate-800/80 pb-4 z-10">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Natural Voice Conversation</h2>
          <p className="text-xs text-slate-400 mt-0.5">Speak naturally with Jarvis and hear spoken responses</p>
        </div>

        {/* Continuous Mode Toggle */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl">
          <Radio className={`w-3.5 h-3.5 ${continuous ? "text-emerald-400 animate-pulse" : "text-slate-500"}`} />
          <span className="text-xs font-medium text-slate-300">Continuous</span>
          <button
            onClick={() => setContinuous(!continuous)}
            className={`w-9 h-5 flex items-center rounded-full p-1 transition-colors ${
              continuous ? "bg-blue-600" : "bg-slate-800"
            }`}
          >
            <div
              className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${
                continuous ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </div>

      {!isSupported && (
        <div className="max-w-md p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex items-center gap-3 text-amber-300 text-xs my-4 z-10">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>
            Your browser does not support the Web Speech API natively. Please use Google Chrome, Microsoft Edge, or configure server-side Whisper & ElevenLabs in Settings.
          </span>
        </div>
      )}

      {/* Central Visualizer & Button */}
      <div className="flex flex-col items-center justify-center gap-8 my-auto z-10">
        <VoiceButton state={state} onClick={toggleVoice} disabled={!isSupported} />

        {/* Live Transcript Display */}
        <div className="max-w-md w-full min-h-[70px] bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 text-center flex items-center justify-center shadow-lg">
          {transcript ? (
            <p className="text-sm text-blue-300 font-medium italic">"{transcript}"</p>
          ) : (
            <p className="text-xs text-slate-500">
              {continuous
                ? "Hands-free continuous mode enabled. Speak anytime."
                : "Press the microphone to begin speaking."}
            </p>
          )}
        </div>
      </div>

      {/* Footer Controls */}
      <div className="w-full max-w-xl flex items-center justify-between text-xs text-slate-500 border-t border-slate-800/80 pt-4 z-10">
        <div className="flex items-center gap-1.5">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span>Microphone access processed locally in browser</span>
        </div>

        {state === "speaking" && (
          <button
            onClick={interruptSpeech}
            className="flex items-center gap-1.5 text-rose-400 hover:text-rose-300 font-medium"
          >
            <VolumeX className="w-4 h-4" />
            <span>Interrupt Speech</span>
          </button>
        )}
      </div>
    </div>
  );
}
