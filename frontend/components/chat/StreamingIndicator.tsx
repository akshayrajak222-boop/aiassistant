"use client";

import React from "react";
import { Bot } from "lucide-react";

export const StreamingIndicator: React.FC<{ assistantName?: string }> = ({
  assistantName = "Jarvis",
}) => {
  return (
    <div className="flex w-full gap-3 py-4 justify-start">
      <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0 text-blue-400">
        <Bot className="w-4 h-4" />
      </div>

      <div className="flex flex-col gap-1.5 items-start">
        <span className="text-xs font-medium text-slate-400 px-1">{assistantName} is thinking...</span>
        <div className="rounded-2xl px-4 py-3 bg-slate-900 border border-slate-800 rounded-tl-none flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.3s]"></div>
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.15s]"></div>
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></div>
        </div>
      </div>
    </div>
  );
};
