"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

export type VoiceState = "idle" | "listening" | "processing" | "speaking" | "interrupted" | "error";

interface UseVoiceOptions {
  onTranscript?: (text: string) => void;
  voiceName?: string;
  speed?: number;
  continuous?: boolean;
  provider?: "browser" | "elevenlabs" | "openai";
}

export function useVoice({
  onTranscript,
  voiceName,
  speed = 1.0,
  continuous = false,
  provider = "browser",
}: UseVoiceOptions = {}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState<string>("");
  const [isSupported, setIsSupported] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const isSpeakingRef = useRef<boolean>(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const currentTranscriptRef = useRef<string>("");
  const dispatchedRef = useRef<boolean>(false);
  const activeUtteranceRef = useRef<any>(null);
  const speechHeartbeatRef = useRef<any>(null);
  const speechTimeoutRef = useRef<any>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = continuous;
    recognition.interimResults = true;
    recognition.lang = (typeof navigator !== "undefined" && navigator.language) || "en-US";

    recognition.onstart = () => {
      // Don't listen to self speaking
      if (isSpeakingRef.current) {
        recognition.stop();
        return;
      }
      setState("listening");
      setErrorMessage(null);
      currentTranscriptRef.current = "";
      dispatchedRef.current = false;
    };

    recognition.onresult = (event: any) => {
      let finalTranscript = "";
      let interimTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      const activeText = finalTranscript || interimTranscript;
      if (activeText) {
        setTranscript(activeText);
        currentTranscriptRef.current = activeText;
      }

      if (finalTranscript && !dispatchedRef.current) {
        dispatchedRef.current = true;
        setState("processing");
        if (onTranscript) {
          onTranscript(finalTranscript);
        }
      }
    };

    recognition.onerror = (event: any) => {
      console.warn("Speech recognition error:", event.error);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setState("error");
        setErrorMessage("Microphone access is blocked. Please click the site icon in your browser address bar and set Microphone to 'Allow'.");
      } else if (event.error !== "no-speech") {
        setState("error");
        setErrorMessage(`Microphone error: ${event.error}`);
      } else {
        setState("idle");
      }
    };

    recognition.onend = () => {
      if (currentTranscriptRef.current && !dispatchedRef.current) {
        dispatchedRef.current = true;
        setState("processing");
        onTranscript?.(currentTranscriptRef.current);
      } else if (state === "listening") {
        setState("idle");
      }
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.stop();
      } catch {}
    };
  }, [continuous, onTranscript]);

  async function startListening() {
    if (isSpeakingRef.current) {
      interruptSpeech();
    }
    setErrorMessage(null);

    // Request audio stream from browser to trigger permission prompt if not yet granted
    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
      } catch (err: any) {
        console.warn("Microphone permission error:", err);
        setState("error");
        setErrorMessage("Microphone access is blocked. Please allow microphone permission in your browser address bar.");
        return;
      }
    }

    if (recognitionRef.current) {
      try {
        setTranscript("");
        currentTranscriptRef.current = "";
        dispatchedRef.current = false;
        recognitionRef.current.start();
      } catch (err: any) {
        console.warn("Recognition already started or error:", err);
      }
    }
  }

  function stopListening() {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    if (currentTranscriptRef.current && !dispatchedRef.current) {
      dispatchedRef.current = true;
      setState("processing");
      onTranscript?.(currentTranscriptRef.current);
    } else {
      setState("idle");
    }
  }

  function fallbackBrowserSpeech(text: string, onEnd?: () => void) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      isSpeakingRef.current = false;
      setState("idle");
      if (onEnd) onEnd();
      return;
    }

    // Clean any prior speech
    if (speechHeartbeatRef.current) clearInterval(speechHeartbeatRef.current);
    if (speechTimeoutRef.current) clearTimeout(speechTimeoutRef.current);
    window.speechSynthesis.cancel();

    // Sanitize text for clear spoken audio (remove markdown, asterisks, brackets, hashes)
    const cleanedText = text
      .replace(/[*#_`~\[\]\(\)>]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (!cleanedText) {
      isSpeakingRef.current = false;
      setState("idle");
      if (onEnd) onEnd();
      return;
    }

    isSpeakingRef.current = true;
    setState("speaking");

    const utterance = new SpeechSynthesisUtterance(cleanedText);
    utterance.rate = speed;

    // Retain strong ref on both component ref and window to prevent Chromium GC bug
    activeUtteranceRef.current = utterance;
    (window as any).__axyActiveUtterance = utterance;

    if (voiceName) {
      const voices = window.speechSynthesis.getVoices();
      const match = voices.find((v) => v.name === voiceName || v.voiceURI === voiceName);
      if (match) utterance.voice = match;
    }

    const cleanup = () => {
      if (speechHeartbeatRef.current) {
        clearInterval(speechHeartbeatRef.current);
        speechHeartbeatRef.current = null;
      }
      if (speechTimeoutRef.current) {
        clearTimeout(speechTimeoutRef.current);
        speechTimeoutRef.current = null;
      }
      activeUtteranceRef.current = null;
      (window as any).__axyActiveUtterance = null;
      isSpeakingRef.current = false;
    };

    utterance.onend = () => {
      cleanup();
      setState("idle");
      if (onEnd) onEnd();
      if (continuous) {
        startListening();
      }
    };

    utterance.onerror = (err) => {
      console.warn("SpeechSynthesis utterance event:", err);
      cleanup();
      setState("idle");
      if (onEnd) onEnd();
    };

    // Chromium SpeechSynthesis heartbeat workaround:
    // Chromium pauses speech after ~10-15s unless poked via pause/resume
    speechHeartbeatRef.current = setInterval(() => {
      if (typeof window !== "undefined" && window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      }
    }, 10000);

    // Watchdog timer: If browser silently drops speech without firing onend, recover safely
    const estimatedDurationMs = Math.max(5000, cleanedText.length * 85 + 3500);
    speechTimeoutRef.current = setTimeout(() => {
      if (isSpeakingRef.current) {
        console.warn("SpeechSynthesis watchdog timeout: auto-recovering to idle state");
        cleanup();
        try { window.speechSynthesis.cancel(); } catch {}
        setState("idle");
        if (onEnd) onEnd();
      }
    }, estimatedDurationMs);

    window.speechSynthesis.speak(utterance);
  }

  async function speak(text: string, onEnd?: () => void) {
    if (typeof window === "undefined") return;

    interruptSpeech();
    isSpeakingRef.current = true;
    setState("speaking");

    // If ElevenLabs or OpenAI provider is specified, request synthesized audio stream
    if (provider === "elevenlabs" || provider === "openai") {
      try {
        const token = localStorage.getItem("access_token");
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${API_BASE_URL}/api/voice/synthesize`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            text,
            voice: voiceName,
            speed,
            provider,
          }),
        });

        if (res.ok) {
          const contentType = res.headers.get("content-type") || "";
          if (contentType.includes("audio")) {
            const blob = await res.blob();
            const audioUrl = URL.createObjectURL(blob);
            const audio = new Audio(audioUrl);
            audioPlayerRef.current = audio;

            audio.onended = () => {
              isSpeakingRef.current = false;
              setState("idle");
              URL.revokeObjectURL(audioUrl);
              audioPlayerRef.current = null;
              if (onEnd) onEnd();
              if (continuous) startListening();
            };

            audio.onerror = (err) => {
              console.warn("Server audio playback error, falling back to browser speech:", err);
              URL.revokeObjectURL(audioUrl);
              fallbackBrowserSpeech(text, onEnd);
            };

            await audio.play();
            return;
          }
        }
      } catch (err) {
        console.warn("Synthesize request error, falling back to browser speech:", err);
      }
    }

    // Default or fallback to Browser Web Speech API
    fallbackBrowserSpeech(text, onEnd);
  }

  function interruptSpeech() {
    if (typeof window !== "undefined") {
      if (speechHeartbeatRef.current) {
        clearInterval(speechHeartbeatRef.current);
        speechHeartbeatRef.current = null;
      }
      if (speechTimeoutRef.current) {
        clearTimeout(speechTimeoutRef.current);
        speechTimeoutRef.current = null;
      }
      activeUtteranceRef.current = null;
      (window as any).__axyActiveUtterance = null;

      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
        audioPlayerRef.current = null;
      }
      if ("speechSynthesis" in window) {
        try { window.speechSynthesis.cancel(); } catch {}
      }
      isSpeakingRef.current = false;
      setState("interrupted");
      setTimeout(() => setState("idle"), 400);
    }
  }

  return {
    state,
    transcript,
    isSupported,
    errorMessage,
    startListening,
    stopListening,
    speak,
    interruptSpeech,
  };
}
