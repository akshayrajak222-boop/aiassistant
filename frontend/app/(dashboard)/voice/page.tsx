"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Shield,
  Radio,
  VolumeX,
  AlertTriangle,
  Activity,
  Cpu,
  Wifi,
  Terminal,
  Zap,
  RotateCcw,
} from "lucide-react";
import { useVoice } from "@/hooks/useVoice";
import { JarvisOrb } from "@/components/voice/JarvisOrb";
import { AxyFace } from "@/components/voice/AxyFace";
import { streamChatSSE, apiRequest } from "@/lib/api";
import { UserSettings } from "@/lib/types";

interface VoiceMessageLog {
  id: string;
  sender: "user" | "jarvis";
  text: string;
  timestamp: string;
}

export default function VoicePage() {
  const [visualMode, setVisualMode] = useState<"face" | "orb">("face");
  const [continuous, setContinuous] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [logs, setLogs] = useState<VoiceMessageLog[]>([]);
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [systemClock, setSystemClock] = useState<string>("");
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Live system clock for HUD
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setSystemClock(now.toTimeString().split(" ")[0] + "." + Math.floor(now.getMilliseconds() / 100));
    };
    updateTime();
    const interval = setInterval(updateTime, 100);
    return () => clearInterval(interval);
  }, []);

  const handleVoiceTranscript = async (text: string) => {
    if (!text.trim() || isAiProcessing) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const userLog: VoiceMessageLog = {
      id: "user-" + Date.now(),
      sender: "user",
      text,
      timestamp: timeStr,
    };
    setLogs((prev) => [...prev, userLog]);
    setIsAiProcessing(true);

    try {
      let accumulatedResponse = "";
      for await (const event of streamChatSSE(text, activeSessionId || undefined)) {
        if (event.type === "conversation_id") {
          setActiveSessionId(event.data.conversation_id);
        } else if (event.type === "text") {
          const chunk = typeof event.data === "object" ? event.data.content : event.data;
          accumulatedResponse += chunk;
        } else if (event.type === "error") {
          console.error("Agent error:", event.data);
        }
      }

      if (accumulatedResponse) {
        const axyLog: VoiceMessageLog = {
          id: "axy-" + Date.now(),
          sender: "jarvis",
          text: accumulatedResponse,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        };
        setLogs((prev) => [...prev, axyLog]);

        // Speak the assistant's reply through the speech synthesis engine
        speak(accumulatedResponse, () => {
          setIsAiProcessing(false);
        });
      } else {
        setIsAiProcessing(false);
      }
    } catch (err) {
      console.error("Voice streaming execution error:", err);
      setIsAiProcessing(false);
    }
  };

  const [voiceSettings, setVoiceSettings] = useState<{ voice_id?: string | null; provider?: "browser" | "elevenlabs" | "openai" }>({});

  useEffect(() => {
    apiRequest<UserSettings>("/api/settings")
      .then((s) => {
        if (s && s.voice_id) {
          setVoiceSettings({ voice_id: s.voice_id, provider: "elevenlabs" });
        }
      })
      .catch(() => {});
  }, []);

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
    voiceName: voiceSettings.voice_id || undefined,
    provider: voiceSettings.provider || "browser",
  });

  const effectiveState = isAiProcessing ? "processing" : state;

  const toggleVoice = () => {
    if (effectiveState === "listening") {
      stopListening();
    } else if (effectiveState === "speaking") {
      interruptSpeech();
    } else {
      startListening();
    }
  };

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="flex flex-col h-full items-center justify-between p-4 md:p-8 bg-slate-950 relative overflow-hidden cyber-grid">
      {/* Hologram Scanlines Overlay */}
      <div className="absolute inset-0 hologram-scanlines z-0 pointer-events-none" />

      {/* Ambient Lighting Orbs */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-cyan-600/10 rounded-full blur-3xl pointer-events-none animate-pulse-slow" />
      <div className="absolute -bottom-20 -left-20 w-[350px] h-[350px] bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Top Futuristic HUD Telemetry Bar */}
      <div className="w-full max-w-4xl flex items-center justify-between border-b border-cyan-500/20 bg-slate-900/60 backdrop-blur-md px-5 py-3 rounded-2xl z-10 shadow-lg">
        {/* Left: System Telemetry */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-cyan-400">
            <Activity className="w-4 h-4 animate-pulse" />
            <span className="font-semibold tracking-wider">AXY-CORE // V2.0</span>
          </div>
          <div className="hidden sm:flex items-center gap-1 text-slate-400">
            <Cpu className="w-3.5 h-3.5 text-blue-400" />
            <span>AI: GEMINI-3.5-FLASH</span>
          </div>
          <div className="hidden md:flex items-center gap-1 text-emerald-400">
            <Wifi className="w-3.5 h-3.5" />
            <span>SYNC: ACTIVE</span>
          </div>
        </div>

        {/* Right: Clock & Mode Switch */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:block font-mono text-xs text-cyan-300/80 bg-slate-950/80 border border-cyan-500/20 px-2.5 py-1 rounded-md">
            {systemClock || "00:00:00.0"}
          </div>

          <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800 px-3 py-1.5 rounded-xl">
            <Radio className={`w-3.5 h-3.5 ${continuous ? "text-emerald-400 animate-pulse" : "text-slate-500"}`} />
            <span className="text-xs font-mono text-slate-300">Continuous</span>
            <button
              onClick={() => setContinuous(!continuous)}
              className={`w-9 h-5 flex items-center rounded-full p-1 transition-colors ${
                continuous ? "bg-cyan-600 shadow-[0_0_10px_#06b6d4]" : "bg-slate-800"
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
      </div>

      {!isSupported && (
        <div className="max-w-md p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex items-center gap-3 text-amber-300 text-xs my-4 z-10 shadow-lg backdrop-blur-md">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>
            Web Speech recognition is not available in this browser. Please use Chrome or Edge for the natural voice experience.
          </span>
        </div>
      )}

      {errorMessage && (
        <div className="max-w-md p-3 bg-rose-500/20 border border-rose-500/40 rounded-2xl flex items-center gap-2.5 text-rose-300 text-xs my-3 z-10 shadow-lg backdrop-blur-md animate-pulse">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Center Area: 3D Holographic Face & Orb Visualizer */}
      <div className="flex flex-col items-center justify-center my-auto z-10 py-2">
        {/* Visual Mode Selector */}
        <div className="flex items-center gap-1 p-1 bg-slate-900/80 border border-slate-800 rounded-xl mb-3 shadow-md z-10 text-xs">
          <button
            onClick={() => setVisualMode("face")}
            className={`px-3 py-1 rounded-lg font-medium transition-all ${
              visualMode === "face"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            3D Avatar Face
          </button>
          <button
            onClick={() => setVisualMode("orb")}
            className={`px-3 py-1 rounded-lg font-medium transition-all ${
              visualMode === "orb"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Holo-Orb
          </button>
        </div>

        {visualMode === "face" ? (
          <AxyFace state={effectiveState} onClick={toggleVoice} disabled={!isSupported} />
        ) : (
          <JarvisOrb state={effectiveState} onClick={toggleVoice} disabled={!isSupported} />
        )}

        {/* Live Speech Recognition Bubble */}
        <div className="max-w-lg w-full min-h-[64px] bg-slate-900/80 backdrop-blur-md border border-cyan-500/30 rounded-2xl p-4 text-center flex items-center justify-center shadow-xl shadow-cyan-950/20 mt-3">
          {transcript ? (
            <p className="text-sm font-mono text-cyan-300 tracking-wide">
              <span className="text-slate-500 mr-2">&gt;</span>
              "{transcript}"
            </p>
          ) : (
            <p className="text-xs font-mono text-slate-400">
              {continuous
                ? "Autonomous listening activated. Speak naturally anytime."
                : "Awaiting voice transmission. Click the core above to speak."}
            </p>
          )}
        </div>
      </div>

      {/* Bottom Area: Speech Log & Controls */}
      <div className="w-full max-w-4xl flex flex-col gap-3 z-10">
        {/* Recent Communication Log HUD */}
        {logs.length > 0 && (
          <div className="max-h-28 overflow-y-auto bg-slate-900/70 backdrop-blur-md border border-slate-800/80 rounded-xl p-3 flex flex-col gap-2 font-mono text-xs">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`flex items-start gap-2 ${
                  log.sender === "user" ? "text-cyan-300" : "text-emerald-300"
                }`}
              >
                <span className="text-[10px] text-slate-500 flex-shrink-0 mt-0.5">[{log.timestamp}]</span>
                <span className="font-bold flex-shrink-0">
                  {log.sender === "user" ? "USER:" : "AXY:"}
                </span>
                <span className="text-slate-200 line-clamp-2">{log.text}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}

        {/* Bottom Status Bar */}
        <div className="w-full flex items-center justify-between text-xs text-slate-500 border-t border-cyan-500/20 pt-3">
          <div className="flex items-center gap-2 font-mono">
            <Shield className="w-3.5 h-3.5 text-cyan-400" />
            <span>ENCRYPTED LOCAL AURAL BUFFER</span>
          </div>

          <div className="flex items-center gap-4">
            {logs.length > 0 && (
              <button
                onClick={() => setLogs([])}
                className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors font-mono"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Clear HUD</span>
              </button>
            )}

            {effectiveState === "speaking" && (
              <button
                onClick={interruptSpeech}
                className="flex items-center gap-1.5 text-rose-400 hover:text-rose-300 font-mono font-medium transition-colors"
              >
                <VolumeX className="w-4 h-4 animate-pulse" />
                <span>INTERRUPT AUDIO</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
