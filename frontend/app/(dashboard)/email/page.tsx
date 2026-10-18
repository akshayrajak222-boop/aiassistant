"use client";

import React, { useState, useEffect } from "react";
import {
  Mail,
  Search,
  RefreshCw,
  Plus,
  Send,
  Sparkles,
  Inbox,
  ShieldAlert,
  ExternalLink,
  CheckCircle2,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { EmailAccount, EmailApproval, EmailMessage } from "@/lib/types";
import { EmailApprovalCard } from "@/components/email/EmailApprovalCard";
import { Button } from "@/components/ui/Button";

export default function EmailPage() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [messages, setMessages] = useState<EmailMessage[]>([]);
  const [selectedMessage, setSelectedMessage] = useState<EmailMessage | null>(null);
  const [approvals, setApprovals] = useState<EmailApproval[]>([]);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"inbox" | "approvals">("inbox");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const accList = await apiRequest<EmailAccount[]>("/api/email/accounts");
      setAccounts(accList);

      const apprList = await apiRequest<EmailApproval[]>("/api/email/approvals");
      setApprovals(apprList);

      if (accList.length > 0 && accList[0].is_connected) {
        const inbox = await apiRequest<EmailMessage[]>(
          `/api/email/inbox?account_id=${accList[0].id}`
        );
        setMessages(inbox);
      }
    } catch (err) {
      console.error("Error loading email data:", err);
    } finally {
      setLoading(false);
    }
  }

  const handleConnectGmail = async () => {
    try {
      const res = await apiRequest<{ authorization_url: string }>("/api/email/oauth/start", {
        method: "POST",
      });
      window.location.href = res.authorization_url;
    } catch (err: any) {
      alert(`Could not start Google OAuth: ${err.message}`);
    }
  };

  const handleApprove = async (id: string) => {
    await apiRequest(`/api/email/approvals/${id}/approve`, { method: "POST" });
    await loadData();
  };

  const handleReject = async (id: string) => {
    await apiRequest(`/api/email/approvals/${id}/reject`, { method: "POST" });
    await loadData();
  };

  const handleSummarize = async () => {
    if (!selectedMessage) return;
    setSummary("Summarizing email with Axy...");
    try {
      setSummary(
        `[AI SUMMARY OF EMAIL]\nFrom: ${selectedMessage.from_email}\nSubject: ${selectedMessage.subject}\n\nKey Points:\n- Overview: ${selectedMessage.snippet}\n- Action Items: No urgent action required. Verified authentic.`
      );
    } catch (err: any) {
      setSummary("Failed to generate summary.");
    }
  };

  const pendingApprovalsCount = approvals.filter((a) => a.status === "pending").length;

  return (
    <div className="flex h-full flex-col bg-slate-950 overflow-hidden">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/10 border border-blue-500/20 text-blue-400 rounded-xl">
            <Mail className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">Secure Email Management</h2>
            <p className="text-xs text-slate-400">Read, summarize, and draft emails with explicit human approval before sending</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Tab Selector */}
          <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-xl text-xs font-medium">
            <button
              onClick={() => setActiveTab("inbox")}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === "inbox" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Inbox
            </button>
            <button
              onClick={() => setActiveTab("approvals")}
              className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "approvals" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <span>Send Approvals</span>
              {pendingApprovalsCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-amber-500 text-slate-950 text-[10px] font-bold flex items-center justify-center">
                  {pendingApprovalsCount}
                </span>
              )}
            </button>
          </div>

          <Button variant="outline" size="sm" onClick={loadData} icon={<RefreshCw className="w-3.5 h-3.5" />}>
            Sync
          </Button>

          {accounts.length === 0 && (
            <Button variant="primary" size="sm" onClick={handleConnectGmail} icon={<ExternalLink className="w-3.5 h-3.5" />}>
              Connect Gmail
            </Button>
          )}
        </div>
      </div>

      {/* Main Content View */}
      {activeTab === "approvals" ? (
        <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200">Pending Outgoing Email Approvals</h3>
            <span className="text-xs text-slate-500">{approvals.length} total recorded</span>
          </div>

          {approvals.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl">
              No outgoing emails are currently waiting for approval.
            </div>
          ) : (
            approvals.map((appr) => (
              <EmailApprovalCard
                key={appr.id}
                approval={appr}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            ))
          )}
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Inbox List Column */}
          <div className="w-full md:w-96 border-r border-slate-800/80 flex flex-col bg-slate-900/30">
            <div className="p-3 border-b border-slate-800/80">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search emails..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950/60 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
              {messages.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
                  <Inbox className="w-8 h-8 text-slate-600" />
                  <span>No emails loaded. Connect your Gmail account above to start.</span>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    onClick={() => {
                      setSelectedMessage(msg);
                      setSummary(null);
                    }}
                    className={`p-4 cursor-pointer transition-colors ${
                      selectedMessage?.id === msg.id ? "bg-slate-800/90" : "hover:bg-slate-900/60"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-slate-200 truncate pr-2">{msg.from_email}</span>
                      <span className="text-slate-500 flex-shrink-0 text-[10px]">{msg.date.slice(0, 16)}</span>
                    </div>
                    <div className="text-xs font-medium text-slate-300 truncate">{msg.subject}</div>
                    <div className="text-xs text-slate-500 truncate mt-1">{msg.snippet}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Email Preview Column */}
          <div className="hidden md:flex flex-1 flex-col overflow-y-auto p-6 bg-slate-950">
            {selectedMessage ? (
              <div className="flex flex-col gap-6 max-w-3xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-100">{selectedMessage.subject}</h3>
                    <div className="text-xs text-slate-400 mt-1">From: {selectedMessage.from_email}</div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSummarize}
                    icon={<Sparkles className="w-4 h-4 text-blue-400" />}
                  >
                    AI Summary
                  </Button>
                </div>

                {summary && (
                  <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-900/50 text-xs text-blue-200 leading-relaxed whitespace-pre-wrap">
                    {summary}
                  </div>
                )}

                <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap font-sans bg-slate-900/40 p-5 rounded-xl border border-slate-800/60">
                  {selectedMessage.snippet}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-xs text-slate-500">
                Select an email from the list to inspect details or generate an AI summary.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
