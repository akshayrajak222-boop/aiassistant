"use client";

import { useEffect, useState, useRef } from "react";
import { apiRequest, streamChatSSE } from "@/lib/api";
import { ConversationDetail, ConversationSummary, Message } from "@/lib/types";

export function useChat() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    } else {
      setMessages([]);
    }
  }, [currentConversationId]);

  async function loadConversations() {
    try {
      const data = await apiRequest<ConversationSummary[]>("/api/conversations");
      setConversations(data);
      if (data.length > 0 && !currentConversationId) {
        setCurrentConversationId(data[0].id);
      }
    } catch (err: any) {
      console.error("Failed to load conversations:", err);
    }
  }

  async function loadConversation(id: string) {
    setLoading(true);
    try {
      const data = await apiRequest<ConversationDetail>(`/api/conversations/${id}`);
      setMessages(data.messages);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function createNewConversation(title: string = "New Conversation") {
    try {
      const newConv = await apiRequest<ConversationSummary>("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      setConversations((prev) => [newConv, ...prev]);
      setCurrentConversationId(newConv.id);
      setMessages([]);
      return newConv.id;
    } catch (err: any) {
      setError(err.message);
      return null;
    }
  }

  async function sendMessage(text: string, modelOverride?: string) {
    if (!text.trim() || isStreaming) return;

    setError(null);
    setIsStreaming(true);

    const tempUserMsg: Message = {
      id: "temp-user-" + Date.now(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    const tempAssistantMsg: Message = {
      id: "temp-assistant-" + Date.now(),
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg, tempAssistantMsg]);

    try {
      let fullAssistantText = "";
      let activeConvId = currentConversationId;

      for await (const event of streamChatSSE(text, activeConvId || undefined, modelOverride)) {
        if (event.type === "conversation_id") {
          activeConvId = event.data.conversation_id;
          if (activeConvId && activeConvId !== currentConversationId) {
            setCurrentConversationId(activeConvId);
            loadConversations();
          }
        } else if (event.type === "text") {
          const chunk = typeof event.data === "object" ? event.data.content : event.data;
          fullAssistantText += chunk;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantMsg.id ? { ...m, content: fullAssistantText } : m
            )
          );
        } else if (event.type === "error") {
          setError(typeof event.data === "object" ? event.data.content : event.data);
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to stream response");
    } finally {
      setIsStreaming(false);
    }
  }

  function stopGeneration() {
    setIsStreaming(false);
  }

  async function deleteConversation(id: string) {
    try {
      await apiRequest(`/api/conversations/${id}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setMessages([]);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  return {
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
    reloadConversations: loadConversations,
  };
}
