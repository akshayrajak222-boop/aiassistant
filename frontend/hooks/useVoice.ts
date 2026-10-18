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
    recognition.lang = "en-US";

    recognition.onstart = () => {
      // Don't listen to self speaking
      if (isSpeakingRef.current) {
        recognition.stop();
        return;
      }
      setState("listening");
      setErrorMessage(null);
    };

    recognition.onresult = (event: any) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          setTranscript(event.results[i][0].transcript);
        }
      }

      if (finalTranscript) {
        setTranscript(finalTranscript);
        setState("processing");
        if (onTranscript) {
          onTranscript(finalTranscript);
        }
      }
    };

    recognition.onerror = (event: any) => {
      if (event.error !== "no-speech") {
        setState("error");
        setErrorMessage(`Microphone error: ${event.error}`);
      } else {
        setState("idle");
      }
    };

    recognition.onend = () => {
      if (state === "listening") {
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

  function startListening() {
    if (isSpeakingRef.current) {
      interruptSpeech();
    }
    if (recognitionRef.current) {
      try {
        setTranscript("");
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
    setState("idle");
  }

  function fallbackBrowserSpeech(text: string, onEnd?: () => void) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      isSpeakingRef.current = false;
      setState("idle");
      if (onEnd) onEnd();
      return;
    }

    window.speechSynthesis.cancel();
    isSpeakingRef.current = true;
    setState("speaking");

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = speed;

    if (voiceName) {
      const voices = window.speechSynthesis.getVoices();
      const match = voices.find((v) => v.name === voiceName || v.voiceURI === voiceName);
      if (match) utterance.voice = match;
    }

    utterance.onend = () => {
      isSpeakingRef.current = false;
      setState("idle");
      if (onEnd) onEnd();
      if (continuous) {
        startListening();
      }
    };

    utterance.onerror = (err) => {
      console.error("SpeechSynthesis error:", err);
      isSpeakingRef.current = false;
      setState("idle");
    };

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
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
        audioPlayerRef.current = null;
      }
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      isSpeakingRef.current = false;
      setState("interrupted");
      setTimeout(() => setState("idle"), 500);
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
