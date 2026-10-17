"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy, Bot, User, Wrench } from "lucide-react";
import { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
  assistantName?: string;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  assistantName = "Jarvis",
}) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex w-full gap-3 py-4 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0 text-blue-400">
          <Bot className="w-4 h-4" />
        </div>
      )}

      <div className={`max-w-[85%] md:max-w-[75%] flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}>
        <div className="flex items-center gap-2 text-xs text-slate-400 px-1">
          <span className="font-medium text-slate-300">{isUser ? "You" : assistantName}</span>
          <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </div>

        <div
          className={`relative group rounded-2xl px-4 py-3 text-sm shadow-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-tr-none"
              : "bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    return (
                      <code
                        className={`${className} bg-slate-950 px-1.5 py-0.5 rounded text-blue-300 font-mono text-xs`}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {/* Copy Button */}
          {!isUser && message.content && (
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 bg-slate-800/80 hover:bg-slate-700 rounded-md text-slate-400 hover:text-white"
              title="Copy response"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>

        {/* Tool Call Badges if present */}
        {message.tool_calls && (
          <div className="flex flex-wrap gap-1.5 mt-1 px-1">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 border border-slate-700 text-blue-400">
              <Wrench className="w-2.5 h-2.5" />
              Tool Executed
            </span>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 text-slate-300">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};
