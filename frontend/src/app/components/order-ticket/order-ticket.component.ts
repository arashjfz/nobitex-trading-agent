import { Component, inject, input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Market } from '../../models';
import { I18nService } from '../../i18n/i18n.service';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-order-ticket',
  imports: [FormsModule],
  template: `
    <section class="ticket">
      <header>
        <h2>{{ i18n.t('order.title') }}</h2>
        @if (dryRun()) {
          <span class="paper">{{ i18n.t('order.paper') }}</span>
        } @else {
          <span class="live">{{ i18n.t('order.live') }}</span>
        }
      </header>

      <div class="side">
        <button type="button" [class.active]="side === 'buy'" (click)="side = 'buy'">
          {{ i18n.t('order.buy') }}
        </button>
        <button type="button" [class.active]="side === 'sell'" (click)="side = 'sell'">
          {{ i18n.t('order.sell') }}
        </button>
      </div>

      <label>
        {{ i18n.t('order.market') }}
        <select [(ngModel)]="market" name="market" dir="ltr">
          <option value="">{{ i18n.t('order.sameAsChart', { symbol: symbol() }) }}</option>
          @for (m of markets(); track m.symbol) {
            <option [value]="m.symbol">{{ m.symbol }}</option>
          }
        </select>
      </label>

      <label>
        {{ i18n.t('order.amount') }}
        <input [(ngModel)]="amount" name="amount" placeholder="0.001" dir="ltr" />
      </label>

      <label>
        {{ i18n.t('order.execution') }}
        <select [(ngModel)]="execution" name="execution">
          <option value="limit">{{ i18n.t('order.limit') }}</option>
          <option value="market">{{ i18n.t('order.marketExec') }}</option>
        </select>
      </label>

      @if (execution === 'limit') {
        <label>
          {{ i18n.t('order.limitPrice') }}
          <input [(ngModel)]="price" name="price" placeholder="60000" dir="ltr" />
        </label>
      }

      <button class="submit" type="button" [disabled]="loading" (click)="submit()">
        {{
          loading
            ? i18n.t('order.placing')
            : side === 'buy'
              ? i18n.t('order.placeBuy')
              : i18n.t('order.placeSell')
        }}
      </button>

      @if (error) {
        <pre class="error">{{ error }}</pre>
      }
      @if (result) {
        <pre class="result">{{ result }}</pre>
      }
    </section>
  `,
  styles: [
    `
      .ticket {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      h2 {
        margin: 0;
        font-size: 15px;
      }
      .paper {
        font-size: 10px;
        padding: 3px 8px;
        border-radius: 999px;
        background: #422006;
        color: #fbbf24;
      }
      .live {
        font-size: 10px;
        padding: 3px 8px;
        border-radius: 999px;
        background: #450a0a;
        color: #f87171;
      }
      .side {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
      }
      .side button {
        padding: 8px;
        border-radius: 8px;
        border: 1px solid #1e293b;
        background: #0b1220;
        color: #94a3b8;
        font-weight: 600;
        cursor: pointer;
      }
      .side button.active:first-child {
        background: #052e1a;
        border-color: #16a34a;
        color: #4ade80;
      }
      .side button.active:last-child {
        background: #2a0f12;
        border-color: #dc2626;
        color: #f87171;
      }
      label {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 11px;
        color: #94a3b8;
      }
      input,
      select {
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 8px;
        color: #e2e8f0;
        padding: 8px 10px;
        font-size: 12.5px;
      }
      input:focus,
      select:focus {
        outline: none;
        border-color: #38bdf8;
      }
      .submit {
        margin-top: 4px;
        padding: 10px;
        border: none;
        border-radius: 8px;
        background: #0284c7;
        color: white;
        font-weight: 600;
        cursor: pointer;
      }
      .submit:disabled {
        background: #1e293b;
        color: #64748b;
        cursor: not-allowed;
      }
      pre {
        margin: 0;
        padding: 8px;
        border-radius: 8px;
        font-size: 11px;
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 180px;
        overflow: auto;
      }
      .error {
        background: #2a0f12;
        color: #fca5a5;
        border: 1px solid #7f1d1d;
      }
      .result {
        background: #0f1f17;
        color: #86efac;
        border: 1px solid #14532d;
      }
    `,
  ],
})
export class OrderTicketComponent {
  readonly symbol = input('BTCUSDT');
  readonly markets = input<Market[]>([]);
  readonly dryRun = input(false);

  private readonly api = inject(ApiService);
  readonly i18n = inject(I18nService);

  side: 'buy' | 'sell' = 'buy';
  market = '';
  amount = '0.001';
  execution: 'limit' | 'market' = 'limit';
  price = '';
  loading = false;
  result: string | null = null;
  error: string | null = null;

  submit(): void {
    this.loading = true;
    this.result = null;
    this.error = null;
    const market = (this.market || this.symbol()).toUpperCase();
    this.api
      .placeOrder({
        symbol: market,
        side: this.side,
        amount: this.amount,
        execution: this.execution,
        price: this.execution === 'limit' ? this.price : null,
      })
      .subscribe({
        next: (response) => {
          this.result = JSON.stringify(response, null, 2);
          this.loading = false;
        },
        error: (err) => {
          this.error = JSON.stringify(err?.error ?? err, null, 2);
          this.loading = false;
        },
      });
  }
}
