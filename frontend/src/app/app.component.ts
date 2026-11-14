import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from './services/api.service';
import { Analysis, Health, Market, ScanResult } from './models';
import { CandleChartComponent } from './components/candle-chart/candle-chart.component';
import { ChatPanelComponent } from './components/chat-panel/chat-panel.component';
import { OrderTicketComponent } from './components/order-ticket/order-ticket.component';

@Component({
  selector: 'app-root',
  imports: [CandleChartComponent, ChatPanelComponent, OrderTicketComponent, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly health = signal<Health | null>(null);
  readonly analysis = signal<Analysis | null>(null);
  readonly scan = signal<ScanResult | null>(null);
  readonly markets = signal<Market[]>([]);
  readonly loading = signal(false);
  readonly scanning = signal(false);
  readonly error = signal<string | null>(null);
  readonly symbol = signal('BTCUSDT');
  readonly resolution = signal('60');
  readonly tab = signal<'chat' | 'order' | 'scan'>('chat');

  readonly resolutions = [
    { value: '15', label: '15m' },
    { value: '60', label: '1h' },
    { value: '240', label: '4h' },
    { value: 'D', label: '1D' },
  ];

  readonly indicatorRows: { key: string; label: string; digits: number }[] = [
    { key: 'ema20', label: 'EMA 20', digits: 4 },
    { key: 'ema50', label: 'EMA 50', digits: 4 },
    { key: 'rsi14', label: 'RSI 14', digits: 2 },
    { key: 'macd_histogram', label: 'MACD histogram', digits: 6 },
    { key: 'bollinger_percent_b', label: 'Bollinger %B', digits: 3 },
    { key: 'atr14', label: 'ATR 14', digits: 4 },
    { key: 'stochastic_k', label: 'Stochastic %K', digits: 2 },
    { key: 'volume_sma20', label: 'Volume SMA20', digits: 2 },
  ];

  ngOnInit(): void {
    this.loadHealth();
    this.loadMarkets();
    this.analyze();
  }

  loadMarkets(): void {
    this.api.markets().subscribe({
      next: (result) => this.markets.set(result.markets),
      error: () => this.markets.set([]),
    });
  }

  loadHealth(): void {
    this.api.health().subscribe({
      next: (health) => this.health.set(health),
      error: () => this.health.set(null),
    });
  }

  analyze(): void {
    const symbol = this.symbol().trim().toUpperCase();
    if (!symbol) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.api.analysis(symbol, this.resolution()).subscribe({
      next: (analysis) => {
        this.analysis.set(analysis);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.describeError(err));
        this.loading.set(false);
      },
    });
  }

  scanMarket(): void {
    this.scanning.set(true);
    this.error.set(null);
    this.api
      .opportunities('BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,BTCIRT,ETHIRT', this.resolution())
      .subscribe({
        next: (result) => {
          this.scan.set(result);
          this.scanning.set(false);
          this.tab.set('scan');
        },
        error: (err) => {
          this.error.set(this.describeError(err));
          this.scanning.set(false);
        },
      });
  }

  selectOpportunity(symbol: string): void {
    this.symbol.set(symbol);
    this.tab.set('chat');
    this.analyze();
  }

  onMarketSelected(symbol: string): void {
    this.symbol.set(symbol);
    this.analyze();
  }

  onResolutionChange(event: Event): void {
    this.resolution.set((event.target as HTMLSelectElement).value);
  }

  fmt(value: number | null | undefined, digits = 6): string {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return '—';
    }
    const abs = Math.abs(value);
    if (abs >= 1000) {
      return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
    }
    if (abs >= 1) {
      return value.toFixed(Math.min(digits, 4));
    }
    return value.toPrecision(4);
  }

  pct(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return '—';
    }
    return `${Math.round(value * 100)}%`;
  }

  signalClass(signal: string): string {
    return signal.toLowerCase();
  }

  time(unixSeconds: number): string {
    if (!unixSeconds) {
      return '—';
    }
    return new Date(unixSeconds * 1000).toLocaleString();
  }

  private describeError(err: unknown): string {
    const payload = (err as { error?: unknown })?.error;
    if (typeof payload === 'string') {
      return payload;
    }
    if (payload && typeof payload === 'object') {
      const detail = (payload as { detail?: unknown }).detail;
      return typeof detail === 'string' ? detail : JSON.stringify(payload);
    }
    return 'Request failed. Is the backend running on port 8000?';
  }
}
