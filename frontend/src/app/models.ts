export interface Candle {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface Market {
  symbol: string;
  src: string;
  dst: string;
  price: number | null;
  change_pct: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
}

export interface ScheduledTask {
  id: string;
  name: string;
  prompt: string;
  cron: string;
  enabled: boolean;
  created_at: number;
  next_run_at: number | null;
  next_run: string | null;
  last_run_at: number | null;
  last_run: string | null;
  last_status: string | null;
  last_result: string | null;
  run_count: number;
}

export interface ScheduleRequest {
  name?: string;
  prompt: string;
  cron: string;
  enabled?: boolean;
}

export interface CronPreview {
  valid: boolean;
  timezone?: string;
  next_runs?: string[];
  error?: string;
}

export interface Analysis {
  symbol: string;
  resolution: string;
  as_of: number;
  last_price: number | null;
  signal: 'BUY' | 'SELL' | 'HOLD';
  score: number;
  confidence: number;
  indicators: Record<string, number | null>;
  levels: {
    entry: number | null;
    stop_loss: number | null;
    take_profit: number | null;
    risk_reward: number;
    support: number | null;
    resistance: number | null;
  };
  reasons: string[];
  candles: Candle[];
}

export interface ScanResult {
  resolution: string;
  opportunities: Analysis[];
  errors: { symbol: string; error: string }[];
}

export interface Health {
  status: string;
  llm: { model: string; configured: boolean };
  nobitex: {
    environment: string;
    base_url: string;
    is_testnet: boolean;
    has_credentials: boolean;
    read_only: boolean;
    dry_run: boolean;
  };
  mcp: { server: string; path: string; exists: boolean; blocked_tools: string[] };
  agent: { max_iterations: number; allow_withdrawals: boolean };
}

export interface OrderRequest {
  symbol: string;
  side: 'buy' | 'sell';
  amount: string;
  execution: 'limit' | 'market' | 'stop_limit' | 'stop_market';
  price?: string | null;
}

export interface AppSettings {
  llm: {
    model: string;
    base_url: string | null;
    temperature: number;
    api_key_set: boolean;
  };
  nobitex: {
    env: string;
    base_url: string;
    base_url_override: string | null;
    token_set: boolean;
    public_key_set: boolean;
    private_key_set: boolean;
    auth_mode: string | null;
    dry_run: boolean;
    read_only: boolean;
  };
  agent: {
    max_iterations: number;
    allow_withdrawals: boolean;
  };
  scheduler: {
    enabled: boolean;
    timezone: string;
  };
}

export interface SettingsUpdate {
  llm_model?: string;
  llm_api_key?: string;
  llm_base_url?: string | null;
  llm_temperature?: number;
  nobitex_env?: 'mainnet' | 'testnet';
  nobitex_base_url?: string | null;
  nobitex_token?: string;
  nobitex_public_key?: string;
  nobitex_private_key?: string;
  nobitex_auth_mode?: 'token' | 'key' | null;
  nobitex_dry_run?: boolean;
  nobitex_read_only?: boolean;
  allow_withdrawals?: boolean;
  agent_max_iterations?: number;
  scheduler_enabled?: boolean;
  scheduler_timezone?: string;
}

export interface ChatEvent {
  type: string;
  id?: string;
  timestamp?: string;
  source?: string;
  text?: string;
  tool_name?: string;
  thought?: string;
  action?: unknown;
  observation?: string;
  data?: unknown;
  summary?: string;
  is_error?: boolean;
  error?: string;
  session_id?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'error' | 'system';
  text: string;
  tool?: string;
  time: number;
  kind?: 'text' | 'action' | 'observation';
  args?: Record<string, unknown>;
  data?: unknown;
  failed?: boolean;
}
