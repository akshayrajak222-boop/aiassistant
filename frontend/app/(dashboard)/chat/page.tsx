"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Plus,
  Trash2,
  StopCircle,
  Paperclip,
  Mic,
  MessageSquare,
  Search,
  Sparkles,
} from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { StreamingIndicator } from "@/components/chat/StreamingIndicator";
import { Button } from "@/components/ui/Button";

export default function ChatPage() {
  const {
    conversations,
    currentConversationId,
    messages,
    isStreaming,
    loading,
    error,
    setCurrentConversationId,
    createNewConversation,
    sendMessage,
    stopGeneration,
    deleteConversation,
  } = useChat();

  const [input, setInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const text = input;
    setInput("");
    sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const starterPrompts = [
    "Check my new emails and summarize important ones",
    "What's the current time and what are my upcoming action items?",
    "Draft a reply to the latest invoice email",
    "What do you remember about my current project preferences?",
  ];

  return (
    <div className="flex h-full w-full overflow-hidden bg-slate-950">
      {/* Conversations Sub-Sidebar */}
      <div className="hidden lg:flex w-72 flex-col bg-slate-900/50 border-r border-slate-800/80">
        <div className="p-3 border-b border-slate-800/80 flex flex-col gap-2.5">
          <Button
            onClick={() => createNewConversation()}
            variant="primary"
            size="sm"
            className="w-full justify-start gap-2 shadow-sm"
            icon={<Plus className="w-4 h-4" />}
          >
            New Conversation
          </Button>

          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950/60 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1">
          {filteredConversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-500">No conversations yet.</div>
          ) : (
            filteredConversations.map((c) => (
              <div
                key={c.id}
                onClick={() => setCurrentConversationId(c.id)}
                className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer text-xs font-medium transition-all ${
                  c.id === currentConversationId
                    ? "bg-slate-800 text-white shadow-sm border border-slate-700/60"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                }`}
              >
                <div className="flex items-center gap-2 truncate pr-2">
                  <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-slate-400" />
                  <span className="truncate">{c.title}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-500 rounded transition-opacity"
                  title="Archive chat"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Stream Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative cyber-grid">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-cyan-600/5 rounded-full blur-3xl pointer-events-none" />
        {/* Messages List */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 flex flex-col">
          {messages.length === 0 && !loading ? (
            <div className="flex-1 flex flex-col items-center justify-center max-w-xl mx-auto text-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <Sparkles className="w-6 h-6" />
              </div>
              <h2 className="text-xl font-bold text-slate-100">How can Axy assist you today?</h2>
              <p className="text-xs text-slate-400 leading-relaxed max-w-md">
                Ask questions, inspect your Gmail inbox, draft client communications, reason through complex tasks, or speak with natural voice.
              </p>

              {/* Starter prompts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full mt-2">
                {starterPrompts.map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInput(p);
                      sendMessage(p);
                    }}
                    className="p-3 text-left bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-xs text-slate-300 hover:text-white transition-all shadow-sm"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl w-full mx-auto flex flex-col divide-y divide-slate-800/40">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} assistantName="Axy" />
              ))}
              {isStreaming && <StreamingIndicator assistantName="Axy" />}
              <div ref={messagesEndRef} />
            </div>
          )}

          {error && (
            <div className="max-w-xl mx-auto my-2 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl text-xs text-center">
              {error}
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-slate-950/80 border-t border-slate-800/80 backdrop-blur-md">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSend} className="relative flex items-end bg-slate-900 border border-slate-800 rounded-2xl p-2 shadow-lg focus-within:border-blue-500 transition-colors">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask Axy anything or give a task..."
                rows={1}
                className="flex-1 bg-transparent border-0 text-slate-100 placeholder-slate-500 text-sm p-2 focus:ring-0 resize-none max-h-32 min-h-[38px] overflow-y-auto"
              />

              <div className="flex items-center gap-1.5 pl-2 pb-0.5">
                {isStreaming ? (
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    onClick={stopGeneration}
                    icon={<StopCircle className="w-4 h-4" />}
                  >
                    Stop
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={!input.trim()}
                    icon={<Send className="w-3.5 h-3.5" />}
                  >
                    Send
                  </Button>
                )}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
