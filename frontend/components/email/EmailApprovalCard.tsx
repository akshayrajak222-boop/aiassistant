"use client";

import React, { useState } from "react";
import { Mail, CheckCircle, XCircle, AlertTriangle, Send } from "lucide-react";
import { EmailApproval } from "@/lib/types";
import { Button } from "@/components/ui/Button";

interface EmailApprovalCardProps {
  approval: EmailApproval;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}

export const EmailApprovalCard: React.FC<EmailApprovalCardProps> = ({
  approval,
  onApprove,
  onReject,
}) => {
  const [loading, setLoading] = useState(false);
  const email = approval.email_data;

  const handleApprove = async () => {
    setLoading(true);
    try {
      await onApprove(approval.id);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    try {
      await onReject(approval.id);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl bg-slate-900 border border-slate-800 p-5 shadow-lg flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
            <Mail className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-100">Outgoing Email Approval Request</h4>
            <p className="text-xs text-slate-400">Queued {new Date(approval.created_at).toLocaleString()}</p>
          </div>
        </div>

        <span
          className={`px-2.5 py-0.5 rounded-full text-xs font-medium uppercase tracking-wider ${
            approval.status === "pending"
              ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
              : approval.status === "executed"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "bg-slate-800 text-slate-400 border border-slate-700"
          }`}
        >
          {approval.status}
        </span>
      </div>

      {/* Recipient & Subject */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-950/60 p-3 rounded-lg border border-slate-800/60">
        <div>
          <span className="text-slate-500 font-medium">To:</span>{" "}
          <span className="text-slate-200 font-semibold">{email.to}</span>
        </div>
        <div>
          <span className="text-slate-500 font-medium">Subject:</span>{" "}
          <span className="text-slate-200 font-semibold">{email.subject}</span>
        </div>
      </div>

      {/* Body Preview */}
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-slate-400">Message Content:</span>
        <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800/60 text-slate-300 text-sm whitespace-pre-wrap font-sans max-h-48 overflow-y-auto">
          {email.body}
        </div>
      </div>

      {/* Security Notice */}
      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-blue-950/40 border border-blue-900/40 text-blue-300 text-xs">
        <AlertTriangle className="w-4 h-4 flex-shrink-0 text-blue-400" />
        <span>Review carefully before approving. The email will be sent immediately upon approval.</span>
      </div>

      {/* Actions */}
      {approval.status === "pending" && (
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReject}
            disabled={loading}
            icon={<XCircle className="w-4 h-4 text-rose-400" />}
          >
            Reject
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleApprove}
            loading={loading}
            icon={<Send className="w-4 h-4" />}
          >
            Approve & Send
          </Button>
        </div>
      )}
    </div>
  );
};
