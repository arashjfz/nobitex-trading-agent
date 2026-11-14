import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Candle } from '../../models';

interface Bar {
  cx: number;
  x: number;
  width: number;
  yOpen: number;
  yClose: number;
  yHigh: number;
  yLow: number;
  color: string;
}

@Component({
  selector: 'app-candle-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe],
  template: `
    <div class="chart-wrap">
      @if (bars().length === 0) {
        <p class="empty">No candles yet.</p>
      } @else {
        <svg [attr.viewBox]="'0 0 ' + width + ' ' + height" preserveAspectRatio="none">
          @for (bar of bars(); track $index) {
            <line
              [attr.x1]="bar.cx"
              [attr.x2]="bar.cx"
              [attr.y1]="bar.yHigh"
              [attr.y2]="bar.yLow"
              [attr.stroke]="bar.color"
              stroke-width="1"
            />
            <rect
              [attr.x]="bar.x"
              [attr.y]="bar.yOpen < bar.yClose ? bar.yOpen : bar.yClose"
              [attr.width]="bar.width"
              [attr.height]="bar.yOpen < bar.yClose ? bar.yClose - bar.yOpen : bar.yOpen - bar.yClose"
              [attr.fill]="bar.color"
            />
          }
        </svg>
        <div class="axis">
          <span>{{ max() | number: '1.0-6' }}</span>
          <span>{{ min() | number: '1.0-6' }}</span>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .chart-wrap {
        position: relative;
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 8px;
      }
      svg {
        width: 100%;
        height: 300px;
        display: block;
      }
      .axis {
        position: absolute;
        top: 8px;
        right: 12px;
        bottom: 8px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        font-size: 11px;
        color: #64748b;
        pointer-events: none;
      }
      .empty {
        height: 300px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #64748b;
        margin: 0;
      }
    `,
  ],
})
export class CandleChartComponent {
  readonly candles = input<Candle[]>([]);
  readonly width = 800;
  readonly height = 320;

  readonly bars = computed<Bar[]>(() => {
    const data = this.candles();
    if (!data.length) {
      return [];
    }
    const highs = data.map((c) => c.h);
    const lows = data.map((c) => c.l);
    const max = Math.max(...highs);
    const min = Math.min(...lows);
    const range = max - min || 1;
    const pad = 10;
    const step = (this.width - pad * 2) / data.length;
    const bodyWidth = Math.max(1.5, step * 0.65);
    const y = (value: number) => pad + ((max - value) / range) * (this.height - pad * 2);

    return data.map((candle, index) => {
      const cx = pad + step * index + step / 2;
      const up = candle.c >= candle.o;
      return {
        cx,
        x: cx - bodyWidth / 2,
        width: bodyWidth,
        yOpen: y(candle.o),
        yClose: y(candle.c),
        yHigh: y(candle.h),
        yLow: y(candle.l),
        color: up ? '#22c55e' : '#ef4444',
      };
    });
  });

  readonly max = computed(() => {
    const data = this.candles();
    return data.length ? Math.max(...data.map((c) => c.h)) : 0;
  });

  readonly min = computed(() => {
    const data = this.candles();
    return data.length ? Math.min(...data.map((c) => c.l)) : 0;
  });
}
