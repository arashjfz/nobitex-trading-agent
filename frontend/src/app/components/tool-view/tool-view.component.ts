import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { ChatMessage } from '../../models';
import { I18nService } from '../../i18n/i18n.service';

interface Level {
  price: number;
  amount: number;
  total: number;
  width: number;
}

interface Book {
  bids: Level[];
  asks: Level[];
  last: number;
  bestBid: number;
  bestAsk: number;
  spread: number;
  spreadPct: number;
  mid: number;
  updated: string;
}

interface AnalysisData {
  symbol: string;
  resolution: string;
  signal: string;
  score: number;
  confidence: number;
  last_price: number | null;
  indicators?: Record<string, number | null>;
  levels?: Record<string, number | null>;
  reasons?: string[];
}

interface ServerInfo {
  environment?: string;
  base_url?: string;
  has_credentials?: boolean;
  auth_mode?: string | null;
  read_only?: boolean;
  dry_run?: boolean;
  paper_balances?: Record<string, string>;
}

interface WalletRow {
  currency: string;
  balance: string;
  active: string;
  blocked: string;
}

interface StatRow {
  market: string;
  last: string;
  change: number;
  high: string;
  low: string;
  volume: string;
  bid: string;
  ask: string;
}

interface OrderRow {
  id: string;
  market: string;
  side: string;
  price: string;
  amount: string;
  status: string;
  time: string;
}

interface TradeRow {
  time: string;
  side: string;
  price: string;
  amount: string;
  total: string;
}

interface Generic {
  scalars: { key: string; value: string }[];
  nested: { key: string; rows: { key: string; value: string }[] }[];
  arrays: { key: string; columns: string[]; rows: Record<string, string>[] }[];
  text: string;
}

type View =
  | 'action'
  | 'orderbook'
  | 'analysis'
  | 'server'
  | 'wallets'
  | 'stats'
  | 'orders'
  | 'trades'
  | 'generic'
  | 'error';

@Component({
  selector: 'app-tool-view',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (view() === 'action') {
      <div class="action">
        <span class="arrow">→</span>
        <span class="tool-name">{{ name() }}</span>
        @for (arg of argList(); track arg.key) {
          <span class="chip">{{ arg.key }} <b>{{ arg.value }}</b></span>
        }
      </div>
      @if (message().text) {
        <details class="reason">
          <summary>{{ i18n.t('tool.reasoning') }}</summary>
          <p dir="auto">{{ message().text }}</p>
        </details>
      }
    } @else {
      <header class="tool-head">
        <span class="tool-name">{{ name() }}</span>
        @if (message().failed) {
          <span class="badge err">{{ i18n.t('tool.error') }}</span>
        } @else {
          <span class="badge ok">{{ i18n.t('tool.result') }}</span>
        }
      </header>

      @switch (view()) {
        @case ('orderbook') {
          @if (book(); as b) {
            <div class="book-head">
              <span>{{ i18n.t('tool.last') }} <b>{{ num(b.last, 2) }}</b></span>
              <span>
                {{ i18n.t('tool.spread') }} <b>{{ num(b.spread, 2) }}</b>
                ({{ num(b.spreadPct, 3) }}%)
              </span>
              <span>{{ i18n.t('tool.mid') }} <b>{{ num(b.mid, 2) }}</b></span>
              @if (b.updated) {
                <span class="muted">{{ b.updated }}</span>
              }
            </div>
            <div class="book">
              <div class="book-col">
                <div class="book-title ask">{{ i18n.t('tool.asks') }}</div>
                <div class="book-row head">
                  <span>{{ i18n.t('tool.price') }}</span>
                  <span>{{ i18n.t('tool.amount') }}</span>
                  <span>{{ i18n.t('tool.total') }}</span>
                </div>
                @for (level of b.asks; track $index) {
                  <div class="book-row">
                    <span class="bar ask" [style.width.%]="level.width"></span>
                    <span>{{ num(level.price, 2) }}</span>
                    <span>{{ num(level.amount, 6) }}</span>
                    <span>{{ num(level.total, 4) }}</span>
                  </div>
                }
              </div>
              <div class="book-col">
                <div class="book-title bid">{{ i18n.t('tool.bids') }}</div>
                <div class="book-row head">
                  <span>{{ i18n.t('tool.price') }}</span>
                  <span>{{ i18n.t('tool.amount') }}</span>
                  <span>{{ i18n.t('tool.total') }}</span>
                </div>
                @for (level of b.bids; track $index) {
                  <div class="book-row">
                    <span class="bar bid" [style.width.%]="level.width"></span>
                    <span>{{ num(level.price, 2) }}</span>
                    <span>{{ num(level.amount, 6) }}</span>
                    <span>{{ num(level.total, 4) }}</span>
                  </div>
                }
              </div>
            </div>
          } @else {
            <pre class="raw">{{ message().text }}</pre>
          }
        }

        @case ('analysis') {
          @if (analysis(); as a) {
            <div class="analysis">
              <div class="signal" [class]="'signal ' + a.signal.toLowerCase()">
                <span class="signal-name">{{ a.signal }}</span>
                <span class="signal-meta">
                  {{
                    i18n.t('tool.signalScore', {
                      score: num(a.score, 2),
                      confidence: num(a.confidence * 100, 0)
                    })
                  }}
                </span>
              </div>
              <div class="price">
                {{ i18n.t('tool.lastPrice') }} <b>{{ num(a.last_price, 2) }}</b>
                <span class="muted">{{ a.symbol }} · {{ resolutionLabel(a.resolution) }}</span>
              </div>
              @if (levelRows().length) {
                <div class="levels">
                  @for (row of levelRows(); track row.key) {
                    <div class="level" [class]="'level ' + row.key">
                      <span>{{ row.label }}</span><b>{{ row.value }}</b>
                    </div>
                  }
                </div>
              }
              @if (indicatorRows().length) {
                <h4>{{ i18n.t('tool.indicators') }}</h4>
                <div class="kv">
                  @for (row of indicatorRows(); track row.key) {
                    <div class="kv-row"><span>{{ row.label }}</span><b>{{ row.value }}</b></div>
                  }
                </div>
              }
              @if (a.reasons?.length) {
                <h4>{{ i18n.t('tool.why') }}</h4>
                <ul class="reasons">
                  @for (reason of a.reasons; track $index) {
                    <li>{{ reason }}</li>
                  }
                </ul>
              }
            </div>
          } @else {
            <pre class="raw">{{ message().text }}</pre>
          }
        }

        @case ('server') {
          @if (server(); as s) {
            <div class="kv">
              <div class="kv-row">
                <span>{{ i18n.t('tool.environment') }}</span><b>{{ s.environment ?? '—' }}</b>
              </div>
              <div class="kv-row">
                <span>{{ i18n.t('tool.baseUrl') }}</span><b dir="ltr">{{ s.base_url ?? '—' }}</b>
              </div>
              <div class="kv-row">
                <span>{{ i18n.t('tool.credentials') }}</span>
                <b>{{ s.has_credentials ? i18n.t('tool.configured') : i18n.t('tool.none') }}</b>
              </div>
              <div class="kv-row">
                <span>{{ i18n.t('tool.authMode') }}</span>
                <b>{{ s.auth_mode || i18n.t('tool.auto') }}</b>
              </div>
              <div class="kv-row">
                <span>{{ i18n.t('tool.readOnly') }}</span>
                <b>{{ s.read_only ? i18n.t('tool.yes') : i18n.t('tool.no') }}</b>
              </div>
              <div class="kv-row">
                <span>{{ i18n.t('tool.dryRun') }}</span>
                <b>{{ s.dry_run ? i18n.t('tool.paperYes') : i18n.t('tool.liveNo') }}</b>
              </div>
            </div>
            @if (balances().length) {
              <h4>{{ i18n.t('tool.paperBalances') }}</h4>
              <div class="chips">
                @for (balance of balances(); track balance.currency) {
                  <span class="chip">{{ balance.currency }} <b>{{ balance.amount }}</b></span>
                }
              </div>
            }
          } @else {
            <pre class="raw">{{ message().text }}</pre>
          }
        }

        @case ('wallets') {
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{{ i18n.t('tool.currency') }}</th>
                  <th>{{ i18n.t('tool.balance') }}</th>
                  <th>{{ i18n.t('tool.active') }}</th>
                  <th>{{ i18n.t('tool.blocked') }}</th>
                </tr>
              </thead>
              <tbody>
                @for (wallet of wallets(); track wallet.currency) {
                  <tr>
                    <td><b>{{ wallet.currency }}</b></td>
                    <td>{{ wallet.balance }}</td>
                    <td>{{ wallet.active }}</td>
                    <td>{{ wallet.blocked }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (paper()) {
            <span class="badge paper">{{ i18n.t('tool.paper') }}</span>
          }
        }

        @case ('stats') {
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{{ i18n.t('tool.market') }}</th>
                  <th>{{ i18n.t('tool.last') }}</th>
                  <th>{{ i18n.t('tool.change24h') }}</th>
                  <th>{{ i18n.t('tool.high') }}</th>
                  <th>{{ i18n.t('tool.low') }}</th>
                  <th>{{ i18n.t('tool.volume') }}</th>
                  <th>{{ i18n.t('tool.bid') }}</th>
                  <th>{{ i18n.t('tool.ask') }}</th>
                </tr>
              </thead>
              <tbody>
                @for (row of statsView(); track row.market) {
                  <tr>
                    <td><b>{{ row.market }}</b></td>
                    <td>{{ row.last }}</td>
                    <td [class]="changeClass(row.change)">{{ num(row.change, 2) }}%</td>
                    <td>{{ row.high }}</td>
                    <td>{{ row.low }}</td>
                    <td>{{ row.volume }}</td>
                    <td>{{ row.bid }}</td>
                    <td>{{ row.ask }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (statsTotal() > statsView().length) {
            <p class="muted">
              {{ i18n.t('tool.showing', { shown: statsView().length, total: statsTotal() }) }}
            </p>
          }
        }

        @case ('orders') {
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{{ i18n.t('tool.id') }}</th>
                  <th>{{ i18n.t('tool.market') }}</th>
                  <th>{{ i18n.t('tool.side') }}</th>
                  <th>{{ i18n.t('tool.price') }}</th>
                  <th>{{ i18n.t('tool.amount') }}</th>
                  <th>{{ i18n.t('tool.status') }}</th>
                  <th>{{ i18n.t('tool.time') }}</th>
                </tr>
              </thead>
              <tbody>
                @for (row of orders(); track $index) {
                  <tr>
                    <td>{{ row.id }}</td>
                    <td><b>{{ row.market }}</b></td>
                    <td [class]="sideClass(row.side)">{{ row.side }}</td>
                    <td>{{ row.price }}</td>
                    <td>{{ row.amount }}</td>
                    <td>{{ row.status }}</td>
                    <td class="muted">{{ row.time }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }

        @case ('trades') {
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{{ i18n.t('tool.time') }}</th>
                  <th>{{ i18n.t('tool.side') }}</th>
                  <th>{{ i18n.t('tool.price') }}</th>
                  <th>{{ i18n.t('tool.amount') }}</th>
                  <th>{{ i18n.t('tool.total') }}</th>
                </tr>
              </thead>
              <tbody>
                @for (row of trades(); track $index) {
                  <tr>
                    <td class="muted">{{ row.time }}</td>
                    <td [class]="sideClass(row.side)">{{ row.side }}</td>
                    <td>{{ row.price }}</td>
                    <td>{{ row.amount }}</td>
                    <td>{{ row.total }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }

        @case ('generic') {
          @if (generic().scalars.length) {
            <div class="kv">
              @for (row of generic().scalars; track row.key) {
                <div class="kv-row"><span>{{ label(row.key) }}</span><b>{{ row.value }}</b></div>
              }
            </div>
          }
          @for (block of generic().nested; track block.key) {
            <div class="section">
              <h4>{{ label(block.key) }}</h4>
              <div class="kv">
                @for (row of block.rows; track row.key) {
                  <div class="kv-row"><span>{{ label(row.key) }}</span><b>{{ row.value }}</b></div>
                }
              </div>
            </div>
          }
          @for (block of generic().arrays; track block.key) {
            <div class="section">
              <h4>{{ label(block.key) }} <span class="muted">{{ block.rows.length }}</span></h4>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      @for (column of block.columns; track column) {
                        <th>{{ label(column) }}</th>
                      }
                    </tr>
                  </thead>
                  <tbody>
                    @for (row of block.rows; track $index) {
                      <tr>
                        @for (column of block.columns; track column) {
                          <td>{{ row[column] }}</td>
                        }
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          }
          @if (!generic().scalars.length && !generic().nested.length && !generic().arrays.length) {
            <pre class="raw">{{ generic().text || message().text || i18n.t('tool.empty') }}</pre>
          }
        }

        @default {
          <pre class="raw">{{ message().text || i18n.t('tool.empty') }}</pre>
        }
      }
    }
  `,
  styles: [
    `
      :host {
        display: block;
        font-size: 12px;
      }
      .tool-head {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }
      .tool-name {
        font-family: ui-monospace, monospace;
        font-size: 11px;
        color: #a5b4fc;
      }
      .badge {
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 2px 6px;
        border-radius: 999px;
      }
      .badge.ok {
        background: #052e1a;
        color: #4ade80;
      }
      .badge.err {
        background: #3f1115;
        color: #fca5a5;
      }
      .badge.paper {
        background: #3b2a06;
        color: #fbbf24;
        margin-top: 6px;
        display: inline-block;
      }
      .action {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
      }
      .arrow {
        color: #38bdf8;
      }
      .chip {
        font-size: 10.5px;
        color: #94a3b8;
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 999px;
        padding: 2px 8px;
      }
      .chip b {
        color: #e2e8f0;
        font-weight: 600;
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .reason {
        margin-top: 6px;
        color: #94a3b8;
        font-size: 11px;
      }
      .reason summary {
        cursor: pointer;
      }
      .reason p {
        margin: 4px 0 0;
        white-space: pre-wrap;
      }
      .book-head {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        font-size: 11px;
        color: #94a3b8;
        margin-bottom: 8px;
      }
      .book-head b {
        color: #e2e8f0;
      }
      .book {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }
      .book-title {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
      }
      .book-title.ask {
        color: #f87171;
      }
      .book-title.bid {
        color: #4ade80;
      }
      .book-row {
        position: relative;
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 6px;
        padding: 2px 4px;
        font-family: ui-monospace, monospace;
        font-size: 11px;
        color: #cbd5e1;
      }
      .book-row.head {
        color: #64748b;
        font-size: 9.5px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .book-row > span:not(.bar) {
        position: relative;
        z-index: 1;
      }
      .bar {
        position: absolute;
        inset-block: 0;
        inset-inline-start: 0;
        inset-inline-end: auto;
        z-index: 0;
        border-radius: 2px;
        opacity: 0.18;
      }
      .bar.ask {
        background: #ef4444;
      }
      .bar.bid {
        background: #22c55e;
      }
      .analysis {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .signal {
        display: flex;
        align-items: baseline;
        gap: 10px;
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid #1e293b;
        background: #0b1220;
      }
      .signal.buy {
        border-color: #166534;
        background: #052e1a;
      }
      .signal.sell {
        border-color: #7f1d1d;
        background: #2a0f12;
      }
      .signal.hold {
        border-color: #854d0e;
        background: #2a1f06;
      }
      .signal-name {
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .signal-meta {
        font-size: 11px;
        color: #94a3b8;
      }
      .price {
        font-size: 12px;
        color: #cbd5e1;
      }
      .price b {
        font-size: 14px;
      }
      .levels {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
        gap: 6px;
      }
      .level {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 6px 8px;
        border-radius: 8px;
        background: #0b1220;
        border: 1px solid #1e293b;
        font-size: 10.5px;
        color: #94a3b8;
      }
      .level b {
        color: #e2e8f0;
        font-size: 12px;
      }
      .level.entry b {
        color: #38bdf8;
      }
      .level.stop_loss b {
        color: #f87171;
      }
      .level.take_profit b {
        color: #4ade80;
      }
      h4 {
        margin: 4px 0 0;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
      }
      .kv {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 4px 12px;
      }
      .kv-row {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        padding: 3px 0;
        border-bottom: 1px solid #111c2e;
        font-size: 11.5px;
      }
      .kv-row span {
        color: #94a3b8;
      }
      .kv-row b {
        color: #e2e8f0;
        font-weight: 600;
        text-align: right;
        word-break: break-word;
      }
      .reasons {
        margin: 0;
        padding-left: 16px;
        color: #cbd5e1;
        font-size: 11.5px;
        line-height: 1.5;
      }
      .section {
        margin-top: 8px;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
      }
      th,
      td {
        border-bottom: 1px solid #1e293b;
        padding: 4px 7px;
        text-align: left;
        white-space: nowrap;
      }
      th {
        color: #64748b;
        font-size: 9.5px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      td {
        color: #cbd5e1;
      }
      .muted {
        color: #64748b;
      }
      .pos {
        color: #4ade80;
      }
      .neg {
        color: #f87171;
      }
      .buy {
        color: #4ade80;
      }
      .sell {
        color: #f87171;
      }
      .raw {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: ui-monospace, monospace;
        font-size: 10.5px;
        color: #cbd5e1;
        max-height: 260px;
        overflow: auto;
      }
      @media (max-width: 720px) {
        .book {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class ToolViewComponent {
  readonly message = input.required<ChatMessage>();
  readonly i18n = inject(I18nService);

  readonly name = computed(() =>
    (this.message().tool ?? 'tool').replace(/^nobitex_nobitex_/, '').replace(/^nobitex_/, ''),
  );

  readonly data = computed<unknown>(() => this.message().data);

  readonly view = computed<View>(() => {
    if (this.message().kind === 'action') {
      return 'action';
    }
    if (this.message().failed) {
      return 'error';
    }
    const name = this.name();
    if (name.includes('orderbook')) {
      return this.book() ? 'orderbook' : 'generic';
    }
    if (name === 'analyze_market' || name.includes('analysis')) {
      return this.analysis() ? 'analysis' : 'generic';
    }
    if (name.includes('server_info')) {
      return this.server() ? 'server' : 'generic';
    }
    if (name.includes('wallet')) {
      const wallets = (this.data() as { wallets?: unknown } | null)?.wallets;
      return Array.isArray(wallets) ? 'wallets' : 'generic';
    }
    if (name.includes('market_stats')) {
      const stats = (this.data() as { stats?: unknown } | null)?.stats;
      return stats && typeof stats === 'object' ? 'stats' : 'generic';
    }
    if (name.includes('order')) {
      return this.orderRows().length ? 'orders' : 'generic';
    }
    if (name.includes('trade')) {
      return this.tradeRows().length ? 'trades' : 'generic';
    }
    return this.data() ? 'generic' : 'error';
  });

  readonly argList = computed(() =>
    Object.entries(this.message().args ?? {})
      .filter(([key, value]) => key !== 'data' && this.meaningful(value))
      .map(([key, value]) => ({
        key,
        value:
          key === 'resolution' ? this.resolutionLabel(String(value)) : this.scalar(value),
      })),
  );

  readonly book = computed<Book | null>(() => {
    const raw = this.data();
    if (!raw || typeof raw !== 'object') {
      return null;
    }
    const data = raw as { bids?: unknown; asks?: unknown; lastTradePrice?: unknown; lastUpdate?: unknown };
    if (!Array.isArray(data.bids) || !Array.isArray(data.asks)) {
      return null;
    }
    const parse = (rows: unknown[]): { price: number; amount: number }[] =>
      rows
        .filter((row): row is unknown[] => Array.isArray(row) && row.length >= 2)
        .map((row) => ({ price: Number(row[0]), amount: Number(row[1]) }))
        .filter((level) => Number.isFinite(level.price) && Number.isFinite(level.amount));
    const bidsRaw = parse(data.bids).slice(0, 8);
    const asksRaw = parse(data.asks).slice(0, 8);
    if (!bidsRaw.length || !asksRaw.length) {
      return null;
    }
    const cumulative = (levels: { price: number; amount: number }[]): Level[] => {
      let total = 0;
      return levels.map((level) => {
        total += level.amount;
        return { ...level, total, width: 0 };
      });
    };
    const bids = cumulative(bidsRaw);
    const asks = cumulative(asksRaw).reverse();
    const max = Math.max(1, ...bids.map((level) => level.total), ...asks.map((level) => level.total));
    const width = (levels: Level[]): Level[] =>
      levels.map((level) => ({ ...level, width: Math.max(2, (level.total / max) * 100) }));
    const bestBid = bidsRaw[0].price;
    const bestAsk = asksRaw[0].price;
    const mid = (bestBid + bestAsk) / 2;
    return {
      bids: width(bids),
      asks: width(asks),
      last: Number(data.lastTradePrice),
      bestBid,
      bestAsk,
      spread: bestAsk - bestBid,
      spreadPct: ((bestAsk - bestBid) / mid) * 100,
      mid,
      updated: this.time(data.lastUpdate),
    };
  });

  readonly analysis = computed<AnalysisData | null>(() => {
    const raw = this.data();
    if (raw && typeof raw === 'object' && 'indicators' in raw) {
      return raw as AnalysisData;
    }
    const marker = 'Raw analysis (JSON):';
    const index = this.message().text.indexOf(marker);
    if (index >= 0) {
      try {
        return JSON.parse(this.message().text.slice(index + marker.length).trim()) as AnalysisData;
      } catch {
        return null;
      }
    }
    return null;
  });

  readonly levelRows = computed(() => {
    const analysis = this.analysis();
    if (!analysis?.levels) {
      return [];
    }
    const labels: Record<string, string> = {
      entry: 'Entry',
      stop_loss: 'Stop loss',
      take_profit: 'Take profit',
      support: 'Support',
      resistance: 'Resistance',
    };
    return Object.entries(analysis.levels)
      .filter(([, value]) => value !== null && value !== undefined)
      .map(([key, value]) => ({
        key,
        label: this.i18n.t('level.' + key, undefined, labels[key] ?? this.label(key)),
        value: this.num(value, 2),
      }));
  });

  readonly indicatorRows = computed(() => {
    const analysis = this.analysis();
    if (!analysis?.indicators) {
      return [];
    }
    const labels: Record<string, string> = {
      rsi14: 'RSI 14',
      macd: 'MACD',
      macd_signal: 'MACD signal',
      macd_histogram: 'MACD histogram',
      ema20: 'EMA 20',
      ema50: 'EMA 50',
      ema200: 'EMA 200',
      bollinger_upper: 'BB upper',
      bollinger_middle: 'BB middle',
      bollinger_lower: 'BB lower',
      bollinger_percent_b: 'BB %B',
      atr14: 'ATR 14',
      stochastic_k: 'Stoch %K',
      stochastic_d: 'Stoch %D',
      volume: 'Volume',
    };
    return Object.entries(analysis.indicators)
      .filter(([, value]) => value !== null && value !== undefined)
      .map(([key, value]) => ({
        key,
        label: this.i18n.t('indicator.' + key, undefined, labels[key] ?? this.label(key)),
        value: this.num(value, 4),
      }));
  });

  readonly server = computed<ServerInfo | null>(() => {
    const raw = this.data();
    if (!raw || typeof raw !== 'object') {
      return null;
    }
    const info = raw as ServerInfo;
    return info.environment || info.base_url ? info : null;
  });

  readonly balances = computed(() =>
    Object.entries(this.server()?.paper_balances ?? {}).map(([currency, amount]) => ({
      currency: currency.toUpperCase(),
      amount: this.num(amount, 4),
    })),
  );

  readonly wallets = computed<WalletRow[]>(() => {
    const raw = this.data();
    if (!raw || typeof raw !== 'object') {
      return [];
    }
    const rows = (raw as { wallets?: unknown }).wallets;
    if (!Array.isArray(rows)) {
      return [];
    }
    return rows
      .filter((row): row is Record<string, unknown> => !!row && typeof row === 'object')
      .map((row) => ({
        currency: String(row['currency'] ?? '').toUpperCase(),
        balance: this.num(row['balance'], 6),
        active: this.num(row['activeBalance'], 6),
        blocked: this.num(row['blockedBalance'], 6),
      }));
  });

  readonly paper = computed(() => Boolean((this.data() as { paper?: unknown } | null)?.paper));

  readonly stats = computed<StatRow[]>(() => {
    const raw = this.data();
    if (!raw || typeof raw !== 'object') {
      return [];
    }
    const stats = (raw as { stats?: unknown }).stats;
    if (!stats || typeof stats !== 'object' || Array.isArray(stats)) {
      return [];
    }
    return Object.entries(stats as Record<string, Record<string, unknown>>).map(([market, row]) => ({
      market: market.toUpperCase(),
      last: this.num(row['latest'], 2),
      change: Number(row['dayChange']),
      high: this.num(row['dayHigh'], 2),
      low: this.num(row['dayLow'], 2),
      volume: this.num(row['volumeDst'], 2),
      bid: this.num(row['bestBuy'], 2),
      ask: this.num(row['bestSell'], 2),
    }));
  });

  readonly statsView = computed(() => this.stats().slice(0, 25));
  readonly statsTotal = computed(() => this.stats().length);

  readonly orders = computed<OrderRow[]>(() => this.orderRows());

  readonly trades = computed<TradeRow[]>(() => this.tradeRows());

  readonly generic = computed<Generic>(() => {
    const raw = this.data();
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return {
        scalars: [],
        nested: [],
        arrays: [],
        text: raw == null ? this.message().text : this.scalar(raw),
      };
    }
    const scalars: { key: string; value: string }[] = [];
    const nested: { key: string; rows: { key: string; value: string }[] }[] = [];
    const arrays: { key: string; columns: string[]; rows: Record<string, string>[] }[] = [];
    for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
      if (key === 'status' && value === 'ok') {
        continue;
      }
      if (!this.meaningful(value)) {
        continue;
      }
      if (Array.isArray(value)) {
        const objects = value.filter(
          (item): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item),
        );
        if (objects.length) {
          const columns = Array.from(new Set(objects.flatMap((item) => Object.keys(item)))).slice(0, 6);
          arrays.push({
            key,
            columns,
            rows: objects.slice(0, 8).map((item) =>
              Object.fromEntries(columns.map((column) => [column, this.scalar(item[column])])),
            ),
          });
        } else {
          scalars.push({ key, value: value.slice(0, 12).map((item) => this.scalar(item)).join(', ') });
        }
        continue;
      }
      if (typeof value === 'object') {
        const rows = Object.entries(value as Record<string, unknown>)
          .filter(([, item]) => this.meaningful(item))
          .slice(0, 10)
          .map(([itemKey, item]) => ({ key: itemKey, value: this.scalar(item) }));
        if (rows.length) {
          nested.push({ key, rows });
        }
        continue;
      }
      scalars.push({ key, value: this.scalar(value) });
    }
    const empty = !scalars.length && !nested.length && !arrays.length;
    return {
      scalars,
      nested,
      arrays,
      text: empty ? this.i18n.t('tool.noRecords') : this.message().text,
    };
  });

  num(value: unknown, digits = 2): string {
    const number = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(number)) {
      return value === null || value === undefined || value === '' ? '—' : String(value);
    }
    return number.toLocaleString('en-US', { maximumFractionDigits: digits });
  }

  label(key: string): string {
    const translated = this.i18n.t('field.' + key, undefined, '');
    if (translated) {
      return translated;
    }
    return key
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .replace(/^./, (character) => character.toUpperCase());
  }

  resolutionLabel(value: string | undefined): string {
    if (!value) {
      return '';
    }
    if (value === 'D' || value === '1D') {
      return '1D';
    }
    const minutes = Number(value);
    if (!Number.isFinite(minutes)) {
      return value;
    }
    if (minutes % 1440 === 0) {
      return `${minutes / 1440}D`;
    }
    if (minutes % 60 === 0) {
      return `${minutes / 60}h`;
    }
    return `${minutes}m`;
  }

  changeClass(change: number): string {
    if (!Number.isFinite(change) || change === 0) {
      return 'muted';
    }
    return change > 0 ? 'pos' : 'neg';
  }

  sideClass(side: string): string {
    const normalized = side.toLowerCase();
    if (normalized.includes('buy')) {
      return 'buy';
    }
    if (normalized.includes('sell')) {
      return 'sell';
    }
    return '';
  }

  private orderRows(): OrderRow[] {
    const raw = this.data();
    if (!raw || typeof raw !== 'object') {
      return [];
    }
    const data = raw as { orders?: unknown; order?: unknown };
    const rows = Array.isArray(data.orders) ? data.orders : data.order ? [data.order] : [];
    return rows
      .filter((row): row is Record<string, unknown> => !!row && typeof row === 'object')
      .map((row) => ({
        id: String(row['id'] ?? row['orderId'] ?? '—'),
        market: String(
          row['symbol'] ??
            (row['srcCurrency'] && row['dstCurrency']
              ? `${row['srcCurrency']}${row['dstCurrency']}`
              : '—'),
        ).toUpperCase(),
        side: String(row['type'] ?? row['side'] ?? '—'),
        price: this.num(row['price'] ?? row['limitPrice'], 2),
        amount: this.num(row['amount'] ?? row['quantity'] ?? row['executedAmount'], 6),
        status: String(row['status'] ?? '—'),
        time: this.time(row['created_at'] ?? row['createdAt'] ?? row['timestamp'] ?? row['updated_at']),
      }));
  }

  private tradeRows(): TradeRow[] {
    const raw = this.data();
    if (!raw || typeof raw !== 'object') {
      return [];
    }
    const rows = (raw as { trades?: unknown }).trades;
    if (!Array.isArray(rows)) {
      return [];
    }
    return rows
      .filter((row): row is Record<string, unknown> => !!row && typeof row === 'object')
      .map((row) => ({
        time: this.time(row['time'] ?? row['timestamp'] ?? row['created_at']),
        side: String(row['type'] ?? row['side'] ?? '—'),
        price: this.num(row['price'], 2),
        amount: this.num(row['amount'] ?? row['quantity'], 6),
        total: this.num(row['total'] ?? row['value'], 2),
      }));
  }

  private time(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '';
    }
    if (typeof value === 'number') {
      const milliseconds = value < 1e12 ? value * 1000 : value;
      return new Date(milliseconds).toLocaleString('en-GB', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      });
    }
    const parsed = Date.parse(String(value));
    if (Number.isFinite(parsed)) {
      return this.time(parsed);
    }
    return String(value);
  }

  private scalar(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (typeof value === 'number') {
      return this.num(value, 6);
    }
    if (typeof value === 'boolean') {
      return value ? 'yes' : 'no';
    }
    if (typeof value === 'string') {
      return value.length > 160 ? `${value.slice(0, 157)}…` : value;
    }
    if (Array.isArray(value)) {
      return value.slice(0, 8).map((item) => this.scalar(item)).join(', ');
    }
    try {
      const text = JSON.stringify(value);
      return text.length > 160 ? `${text.slice(0, 157)}…` : text;
    } catch {
      return String(value);
    }
  }

  private meaningful(value: unknown): boolean {
    return (
      value !== null &&
      value !== undefined &&
      value !== '' &&
      !(Array.isArray(value) && value.length === 0)
    );
  }
}
