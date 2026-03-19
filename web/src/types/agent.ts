export type AgentStatus = 'active' | 'idle' | 'error' | 'paused';

export interface Agent {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  avatar_url?: string;
  avatar_emoji?: string;
  is_social_active?: boolean;
  status: AgentStatus;
  model: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  schedule_type: 'manual' | 'cron' | 'event';
  schedule_cron?: string;
  schedule_event?: string;
  scenario?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  tg_thread_id?: number | null;
  tg_group_id?: string | null;
  bot_username?: string | null;
  // UI helpers (computed client-side or from tasks)
  tasksToday?: number;
  avatarIcon?: string;
  avatarColor?: string;
}

export interface ModelInfo {
  id: string;
  label: string;
  provider: string;
  context_window: number;
  supports_tools: boolean;
  tier: 'free' | 'premium';
  description: string;
  available: boolean;
  badge?: string;
}

export interface RunResult {
  task_id: string;
  output: string;
  tools_used: string[];
  tokens_used: number;
  status: string;
  model: string;
  provider: string;
}

export interface Task {
  id: string;
  agent_id: string;
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
  input_data?: Record<string, any>;
  output_data?: Record<string, any>;
  error_msg?: string;
  tokens_used: number;
  duration_ms?: number;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}
