export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface UserSettings {
  assistant_name: string;
  system_instructions: string | null;
  preferred_language: string;
  response_style: string;
  voice_id: string | null;
  timezone: string;
  default_model: string | null;
  ai_provider: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_calls?: any;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface ConversationDetail {
  id: string;
  title: string;
  created_at: string;
  is_archived: boolean;
  messages: Message[];
}

export interface EmailAccount {
  id: string;
  provider: "gmail" | "outlook";
  email_address: string;
  is_connected: boolean;
  last_synced_at: string | null;
  created_at: string;
}

export interface EmailMessage {
  id: string;
  thread_id: string;
  subject: string;
  from_email: string;
  to_emails: string[];
  date: string;
  snippet: string;
  is_read: boolean;
  labels: string[];
  body_text?: string;
}

export interface EmailApproval {
  id: string;
  action_type: "send" | "delete" | "archive" | "move";
  email_data: {
    account_id?: string;
    to: string;
    subject: string;
    body: string;
    sent_message_id?: string;
  };
  status: "pending" | "approved" | "rejected" | "executed";
  created_at: string;
  decided_at: string | null;
}

export interface MemoryEntry {
  id: string;
  entry_type: "preference" | "fact" | "summary" | "task";
  content: string;
  tags: string[];
  created_at: string;
  source_conversation_id: string | null;
}

export interface VoiceInfo {
  id: string;
  name: string;
  language: string;
  gender: string | null;
  provider: string;
}
