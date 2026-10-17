"use client";

import { useEffect, useRef, useState } from "react";

export type VoiceState = "idle" | "listening" | "processing" | "speaking" | "interrupted" | "error";

interface UseVoiceOptions {
  onTranscript?: (text: string) => void;
  voiceName?: string;
  speed?: number;
  continuous?: boolean;
}

export function useVoice({
  onTranscript,
  voiceName,
  speed = 1.0,
  continuous = false,
}: UseVoiceOptions = {}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState<string>("");
  const [isSupported, setIsSupported] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const isSpeakingRef = useRef<boolean>(false);

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

  function speak(text: string, onEnd?: () => void) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

    window.speechSynthesis.cancel(); // Stop any pending speech
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

  function interruptSpeech() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
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
