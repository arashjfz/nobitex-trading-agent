export interface Candle {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
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
}
