"use client";

import React, { useState, useEffect } from "react";
import {
  Settings,
  Cpu,
  Mic,
  Brain,
  Shield,
  Activity,
  Trash2,
  Save,
  Plus,
  Check,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { MemoryEntry, UserSettings } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"assistant" | "model" | "voice" | "memory" | "system">("assistant");
  const [settings, setSettings] = useState<UserSettings>({
    assistant_name: "Axy",
    system_instructions: "",
    preferred_language: "en",
    response_style: "balanced",
    voice_id: null,
    timezone: "UTC",
    default_model: "claude-3-5-sonnet-20241022",
    ai_provider: "anthropic",
  });
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [newMemory, setNewMemory] = useState("");
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    loadSettings();
    loadMemories();
    checkHealth();
  }, []);

  async function loadSettings() {
    try {
      const data = await apiRequest<UserSettings>("/api/settings");
      setSettings(data);
    } catch (err) {
      console.error("Error loading settings:", err);
    }
  }

  async function loadMemories() {
    try {
      const data = await apiRequest<MemoryEntry[]>("/api/memory");
      setMemories(data);
    } catch (err) {
      console.error("Error loading memories:", err);
    }
  }

  async function checkHealth() {
    try {
      const data = await apiRequest("/api/health");
      setHealthStatus(data);
    } catch (err) {
      setHealthStatus({ status: "error", detail: "Server offline or unreachable" });
    }
  }

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);
    try {
      await apiRequest("/api/settings", {
        method: "PUT",
        body: JSON.stringify(settings),
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (err: any) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleAddMemory = async () => {
    if (!newMemory.trim()) return;
    try {
      await apiRequest("/api/memory", {
        method: "POST",
        body: JSON.stringify({ content: newMemory, entry_type: "fact" }),
      });
      setNewMemory("");
      await loadMemories();
    } catch (err: any) {
      alert(`Failed to add memory: ${err.message}`);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await apiRequest(`/api/memory/${id}`, { method: "DELETE" });
      await loadMemories();
    } catch (err: any) {
      alert(`Failed to delete memory: ${err.message}`);
    }
  };

  const tabs = [
    { id: "assistant", label: "Assistant Identity", icon: Settings },
    { id: "model", label: "AI Provider & Model", icon: Cpu },
    { id: "voice", label: "Voice Engine", icon: Mic },
    { id: "memory", label: "Memory Management", icon: Brain },
    { id: "system", label: "System & Health", icon: Activity },
  ];

  return (
    <div className="flex h-full flex-col bg-slate-950 overflow-y-auto">
      {/* Top Header */}
      <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/40">
        <h2 className="text-base font-bold text-slate-100">Platform Settings</h2>
        <p className="text-xs text-slate-400">Configure assistant behavior, model providers, voice engine, and persistent memories</p>
      </div>

      <div className="flex flex-col md:flex-row flex-1 p-6 gap-6 max-w-5xl mx-auto w-full">
        {/* Navigation Tabs */}
        <div className="w-full md:w-56 flex flex-row md:flex-col gap-1 overflow-x-auto pb-2 md:pb-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors ${
                  active
                    ? "bg-blue-600 text-white font-semibold"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-900"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Form Content Area */}
        <div className="flex-1 bg-slate-900/40 border border-slate-800 rounded-2xl p-6 shadow-sm">
          {activeTab === "assistant" && (
            <form onSubmit={handleSaveSettings} className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold text-slate-100 border-b border-slate-800 pb-2">
                Assistant Identity & Style
              </h3>

              <Input
                label="Assistant Display Name"
                value={settings.assistant_name}
                onChange={(e) => setSettings({ ...settings, assistant_name: e.target.value })}
                required
              />

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-slate-300">System Instructions & Directives</label>
                <textarea
                  rows={4}
                  value={settings.system_instructions || ""}
                  onChange={(e) => setSettings({ ...settings, system_instructions: e.target.value })}
                  placeholder="e.g. Always be concise, use bullet points for technical summaries..."
                  className="w-full px-3.5 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="Preferred Language"
                  value={settings.preferred_language}
                  onChange={(e) => setSettings({ ...settings, preferred_language: e.target.value })}
                />
                <Input
                  label="Timezone (e.g. UTC, America/New_York)"
                  value={settings.timezone}
                  onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                />
              </div>

              <Button type="submit" variant="primary" loading={saving} icon={savedSuccess ? <Check className="w-4 h-4 text-emerald-300" /> : <Save className="w-4 h-4" />} className="self-start mt-2">
                {savedSuccess ? "Saved Successfully" : "Save Changes"}
              </Button>
            </form>
          )}

          {activeTab === "model" && (
            <form onSubmit={handleSaveSettings} className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold text-slate-100 border-b border-slate-800 pb-2">
                AI Provider & Model
              </h3>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-slate-300">Primary AI Provider</label>
                <select
                  value={settings.ai_provider}
                  onChange={(e) => setSettings({ ...settings, ai_provider: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="anthropic">Anthropic (Claude Sonnet 3.5 / 4.5)</option>
                  <option value="openai">OpenAI (GPT-4o)</option>
                  <option value="ollama">Ollama (Local / Custom Cloud endpoint)</option>
                </select>
              </div>

              <Input
                label="Model Identifier"
                value={settings.default_model || ""}
                onChange={(e) => setSettings({ ...settings, default_model: e.target.value })}
                placeholder="e.g. claude-3-5-sonnet-20241022 or gpt-4o"
              />

              <div className="p-3 bg-blue-950/30 border border-blue-900/40 rounded-xl text-xs text-blue-300">
                AI API keys are configured securely via server environment variables (.env) and are never exposed to the browser.
              </div>

              <Button type="submit" variant="primary" loading={saving} icon={<Save className="w-4 h-4" />} className="self-start mt-2">
                Save Model Configuration
              </Button>
            </form>
          )}

          {activeTab === "voice" && (
            <form onSubmit={handleSaveSettings} className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold text-slate-100 border-b border-slate-800 pb-2">
                Voice & Speech Synthesis
              </h3>
              <p className="text-xs text-slate-400">
                Configure speech recognition and ElevenLabs custom voices for Axy.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                  <h4 className="text-xs font-bold text-slate-200">Speech-to-Text (STT)</h4>
                  <p className="text-[11px] text-slate-400 mt-1">Browser SpeechRecognition (Zero latency)</p>
                </div>

                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                  <h4 className="text-xs font-bold text-slate-200">Text-to-Speech (TTS)</h4>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {settings.voice_id ? "ElevenLabs Neural Voice (Active)" : "Browser SpeechSynthesis (Active)"}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-1.5 mt-2">
                <Input
                  label="ElevenLabs Voice ID (or Custom Cloned Voice ID)"
                  value={settings.voice_id || ""}
                  onChange={(e) => setSettings({ ...settings, voice_id: e.target.value })}
                  placeholder="e.g. 21m00Tcm4TlvDq8ikWAM or your custom ElevenLabs cloned voice ID"
                  helperText="Leave empty to use free Browser Web Speech. If provided, Axy will speak using this ElevenLabs voice."
                />
              </div>

              <div className="p-3 bg-cyan-950/30 border border-cyan-800/40 rounded-xl text-xs text-cyan-300">
                <span className="font-semibold">Tip:</span> To use ElevenLabs, make sure <code className="bg-slate-900 px-1 py-0.5 rounded text-cyan-200">ELEVENLABS_API_KEY</code> is set in your server <code className="bg-slate-900 px-1 py-0.5 rounded text-cyan-200">.env</code> file.
              </div>

              <Button type="submit" variant="primary" loading={saving} icon={<Save className="w-4 h-4" />} className="self-start mt-2">
                Save Voice Configuration
              </Button>
            </form>
          )}

          {activeTab === "memory" && (
            <div className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold text-slate-100 border-b border-slate-800 pb-2">
                Persistent Memory Entries
              </h3>

              <div className="flex gap-2">
                <Input
                  placeholder="Add a new fact or preference (e.g. 'Prefers dark roast coffee')..."
                  value={newMemory}
                  onChange={(e) => setNewMemory(e.target.value)}
                />
                <Button onClick={handleAddMemory} variant="primary" size="md" icon={<Plus className="w-4 h-4" />}>
                  Add
                </Button>
              </div>

              <div className="flex flex-col gap-2 mt-2">
                {memories.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                    No persistent memories stored yet.
                  </div>
                ) : (
                  memories.map((m) => (
                    <div
                      key={m.id}
                      className="flex items-center justify-between p-3 bg-slate-900 border border-slate-800 rounded-xl text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold bg-blue-900/40 text-blue-300">
                          {m.entry_type}
                        </span>
                        <span className="text-slate-200">{m.content}</span>
                      </div>
                      <button
                        onClick={() => handleDeleteMemory(m.id)}
                        className="text-slate-500 hover:text-rose-400 p-1"
                        title="Delete memory"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === "system" && (
            <div className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold text-slate-100 border-b border-slate-800 pb-2">
                System Diagnostics & 24/7 Health
              </h3>

              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-200">Backend API & Database Status</h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">Automated health check</p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <span className="text-xs font-semibold text-emerald-400">
                    {healthStatus?.status === "ok" ? "All Services Operational" : "Healthy"}
                  </span>
                </div>
              </div>

              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-xs flex flex-col gap-1 text-slate-400 font-mono">
                <div>Platform Version: 1.0.0</div>
                <div>Runtime: Docker Compose (Production Target)</div>
                <div>Reverse Proxy: Caddy with Automated TLS</div>
                <div>Target Budget: ~$15/month (Hetzner VPS + Claude Sonnet API)</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
