import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Candle } from '../../models';
import { I18nService } from '../../i18n/i18n.service';

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

interface VolumeBar {
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
}

interface PriceTick {
  value: number;
  y: number;
  top: number;
}

interface TimeTick {
  left: number;
  label: string;
}

interface ChartRange {
  start: number;
  end: number;
}

interface ChartDomain {
  min: number;
  max: number;
}

interface DragBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

@Component({
  selector: 'app-candle-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe],
  template: `
    <div class="chart-wrap" (wheel)="onWheel($event)">
      @if (bars().length === 0) {
        <p class="empty">{{ i18n.t('chart.empty') }}</p>
      } @else {
        <div class="zoom">
          <button type="button" (click)="zoomOut()" [disabled]="!canZoomOut()" aria-label="Zoom out">
            −
          </button>
          <span>{{ zoomLabel() }}×</span>
          <button type="button" (click)="zoomIn()" [disabled]="!canZoomIn()" aria-label="Zoom in">
            +
          </button>
          <button type="button" class="reset" (click)="resetZoom()" aria-label="Reset zoom">
            ⟲
          </button>
        </div>
        <svg
          [attr.viewBox]="'0 0 ' + width + ' ' + height"
          preserveAspectRatio="none"
          (pointerdown)="onPointerDown($event)"
          (pointermove)="onPointerMove($event)"
          (pointerup)="onPointerUp($event)"
          (pointercancel)="onPointerCancel()"
        >
          <defs>
            <linearGradient id="chartGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.09" />
              <stop offset="100%" stop-color="#38bdf8" stop-opacity="0" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" [attr.width]="width" [attr.height]="height" fill="url(#chartGlow)" />
          @for (x of gridX(); track $index) {
            <line
              [attr.x1]="x"
              [attr.x2]="x"
              [attr.y1]="pad"
              [attr.y2]="height - pad"
              stroke="#1e293b"
              stroke-width="1"
              stroke-dasharray="3 6"
              vector-effect="non-scaling-stroke"
            />
          }
          @for (tick of priceTicks(); track $index) {
            <line
              [attr.x1]="pad"
              [attr.x2]="width - pad"
              [attr.y1]="tick.y"
              [attr.y2]="tick.y"
              stroke="#1e293b"
              stroke-width="1"
              stroke-dasharray="3 6"
              vector-effect="non-scaling-stroke"
            />
          }
          @for (bar of bars(); track $index) {
            <line
              [attr.x1]="bar.cx"
              [attr.x2]="bar.cx"
              [attr.y1]="bar.yHigh"
              [attr.y2]="bar.yLow"
              [attr.stroke]="bar.color"
              stroke-width="1.2"
              vector-effect="non-scaling-stroke"
            />
            <rect
              [attr.x]="bar.x"
              [attr.y]="bar.yOpen < bar.yClose ? bar.yOpen : bar.yClose"
              [attr.width]="bar.width"
              [attr.height]="bar.yOpen < bar.yClose ? bar.yClose - bar.yOpen : bar.yOpen - bar.yClose"
              [attr.fill]="bar.color"
              rx="0.5"
            />
          }
          @for (bar of volumeBars(); track $index) {
            <rect
              [attr.x]="bar.x"
              [attr.y]="bar.y"
              [attr.width]="bar.width"
              [attr.height]="bar.height"
              [attr.fill]="bar.color"
              opacity="0.18"
            />
          }
          @if (selectionRect(); as box) {
            <rect
              [attr.x]="box.x"
              [attr.y]="box.y"
              [attr.width]="box.width"
              [attr.height]="box.height"
              fill="rgba(56, 189, 248, 0.12)"
              stroke="#38bdf8"
              stroke-width="1"
              stroke-dasharray="4 3"
              vector-effect="non-scaling-stroke"
              pointer-events="none"
            />
          }
          <line
            [attr.x1]="pad"
            [attr.x2]="width - pad"
            [attr.y1]="lastPriceY()"
            [attr.y2]="lastPriceY()"
            [attr.stroke]="lastColor()"
            stroke-width="1"
            stroke-dasharray="7 4"
            opacity="0.7"
            vector-effect="non-scaling-stroke"
          />
          <circle
            [attr.cx]="width - pad"
            [attr.cy]="lastPriceY()"
            r="3"
            [attr.fill]="lastColor()"
          />
        </svg>
        <div class="axis">
          @for (tick of priceTicks(); track $index) {
            <span [style.top.%]="tick.top">{{ tick.value | number: '1.0-6' }}</span>
          }
        </div>
        <div class="last" [class.down]="lastColor() === '#ef4444'" [style.top.%]="lastPriceTop()">
          {{ lastPrice() | number: '1.0-6' }}
        </div>
        <div class="time-axis">
          @for (tick of timeTicks(); track $index) {
            <span [style.left.%]="tick.left">{{ tick.label }}</span>
          }
        </div>
      }
    </div>
  `,
  styles: [
    `
      .chart-wrap {
        position: relative;
        background:
          radial-gradient(circle at 72% 12%, rgba(56, 189, 248, 0.08), transparent 42%),
          linear-gradient(180deg, #0d1728 0%, #0b1220 100%);
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 8px;
        overflow: hidden;
        transition: border-color 160ms ease;
      }
      .chart-wrap:hover {
        border-color: #334155;
      }
      svg {
        width: 100%;
        height: 300px;
        display: block;
        overflow: visible;
        cursor: crosshair;
        touch-action: none;
        user-select: none;
      }
      .zoom {
        position: absolute;
        top: 9px;
        left: 10px;
        z-index: 2;
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 3px 5px;
        border: 1px solid #1e293b;
        border-radius: 999px;
        background: rgba(9, 16, 28, 0.82);
        backdrop-filter: blur(6px);
      }
      .zoom button {
        width: 20px;
        height: 20px;
        display: grid;
        place-items: center;
        border: 1px solid transparent;
        border-radius: 999px;
        background: transparent;
        color: #cbd5e1;
        font-size: 13px;
        line-height: 1;
        cursor: pointer;
      }
      .zoom button:hover:not(:disabled) {
        background: #111c2e;
        border-color: #334155;
        color: #7dd3fc;
      }
      .zoom button:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
      .zoom .reset {
        font-size: 11px;
      }
      .zoom span {
        min-width: 22px;
        text-align: center;
        font-size: 9px;
        color: #7dd3fc;
        font-variant-numeric: tabular-nums;
      }
      .axis {
        position: absolute;
        top: 8px;
        right: 2px;
        bottom: 8px;
        width: 64px;
        font-size: 10px;
        color: #64748b;
        pointer-events: none;
        font-variant-numeric: tabular-nums;
      }
      .axis span {
        position: absolute;
        right: 0;
        transform: translateY(-50%);
        padding: 0 3px;
        background: #0b1220;
        border-radius: 2px;
        white-space: nowrap;
      }
      .last {
        position: absolute;
        right: 68px;
        transform: translateY(-50%);
        padding: 1px 5px;
        border-radius: 3px;
        background: #22c55e;
        color: #04121f;
        font-size: 9px;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        pointer-events: none;
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.35);
      }
      .last.down {
        background: #ef4444;
        color: #fff;
        box-shadow: 0 0 10px rgba(239, 68, 68, 0.35);
      }
      .time-axis {
        position: relative;
        height: 18px;
        margin-top: 2px;
        font-size: 9px;
        color: #64748b;
        pointer-events: none;
        font-variant-numeric: tabular-nums;
      }
      .time-axis span {
        position: absolute;
        top: 2px;
        transform: translateX(-50%);
        white-space: nowrap;
      }
      .time-axis span:first-child {
        transform: none;
      }
      .time-axis span:last-child {
        transform: translateX(-100%);
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
  readonly i18n = inject(I18nService);
  readonly width = 800;
  readonly height = 320;
  readonly pad = 10;
  readonly volumeHeight = 46;
  readonly zoom = signal(1);
  readonly range = signal<ChartRange | null>(null);
  readonly yDomain = signal<ChartDomain | null>(null);
  readonly drag = signal<DragBox | null>(null);
  readonly timeFormatter = computed(
    () =>
      new Intl.DateTimeFormat(this.i18n.intl(), {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
  );

  readonly visible = computed<Candle[]>(() => {
    const data = this.candles();
    if (!data.length) {
      return [];
    }
    const selected = this.range();
    if (selected) {
      const start = Math.max(0, Math.min(selected.start, data.length - 1));
      const end = Math.max(start, Math.min(selected.end, data.length - 1));
      return data.slice(start, end + 1);
    }
    const count = Math.max(8, Math.ceil(data.length / this.zoom()));
    return data.slice(-count);
  });

  readonly visibleStart = computed(() => {
    const total = this.candles().length;
    const selected = this.range();
    if (selected) {
      return Math.max(0, Math.min(selected.start, total - 1));
    }
    return Math.max(0, total - this.visible().length);
  });

  readonly zoomLabel = computed(() => {
    const total = this.candles().length;
    const count = this.visible().length;
    return total && count ? Math.max(1, Math.round(total / count)) : 1;
  });

  readonly canZoomIn = computed(() => {
    const selected = this.range();
    if (selected) {
      return selected.end - selected.start + 1 > 8;
    }
    return this.zoom() < 16 && this.visible().length > 8;
  });

  readonly canZoomOut = computed(() => {
    if (this.range()) {
      return true;
    }
    return this.zoom() > 1;
  });

  readonly bars = computed<Bar[]>(() => {
    const data = this.visible();
    if (!data.length) {
      return [];
    }
    const max = this.max();
    const min = this.min();
    const range = max - min || 1;
    const step = (this.width - this.pad * 2) / data.length;
    const bodyWidth = Math.max(1.5, step * 0.65);
    const bottom = this.height - this.pad - this.volumeHeight;
    const y = (value: number) =>
      this.pad + ((max - value) / range) * (bottom - this.pad);

    return data.map((candle, index) => {
      const cx = this.pad + step * index + step / 2;
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

  readonly volumeBars = computed<VolumeBar[]>(() => {
    const data = this.visible();
    if (!data.length) {
      return [];
    }
    const maxVolume = Math.max(...data.map((candle) => candle.v), 1);
    const step = (this.width - this.pad * 2) / data.length;
    const bodyWidth = Math.max(1.5, step * 0.65);
    return data.map((candle, index) => {
      const height = (candle.v / maxVolume) * this.volumeHeight;
      const cx = this.pad + step * index + step / 2;
      return {
        x: cx - bodyWidth / 2,
        y: this.height - this.pad - height,
        width: bodyWidth,
        height,
        color: candle.c >= candle.o ? '#22c55e' : '#ef4444',
      };
    });
  });

  readonly max = computed(() => {
    const domain = this.yDomain();
    if (domain) {
      return domain.max;
    }
    const data = this.visible();
    return data.length ? Math.max(...data.map((c) => c.h)) : 0;
  });

  readonly min = computed(() => {
    const domain = this.yDomain();
    if (domain) {
      return domain.min;
    }
    const data = this.visible();
    return data.length ? Math.min(...data.map((c) => c.l)) : 0;
  });

  readonly priceTicks = computed<PriceTick[]>(() => {
    const max = this.max();
    const min = this.min();
    const range = max - min || 1;
    const bottom = this.height - this.pad - this.volumeHeight;
    const count = 5;
    return Array.from({ length: count }, (_, index) => {
      const ratio = index / (count - 1);
      const value = max - range * ratio;
      const y = this.pad + ratio * (bottom - this.pad);
      return { value, y, top: (y / this.height) * 100 };
    });
  });

  readonly gridX = computed(() =>
    Array.from(
      { length: 5 },
      (_, index) => this.pad + (index / 4) * (this.width - this.pad * 2),
    ),
  );

  readonly timeTicks = computed<TimeTick[]>(() => {
    const data = this.visible();
    if (!data.length) {
      return [];
    }
    const last = data.length - 1;
    return this.gridX().map((x) => {
      const ratio = (x - this.pad) / (this.width - this.pad * 2);
      const index = Math.max(0, Math.min(last, Math.round(ratio * last)));
      return {
        left: (x / this.width) * 100,
        label: this.formatTime(data[index].t),
      };
    });
  });

  readonly selectionRect = computed<SelectionRect | null>(() => {
    const box = this.drag();
    if (!box) {
      return null;
    }
    return {
      x: Math.min(box.x1, box.x2),
      y: Math.min(box.y1, box.y2),
      width: Math.abs(box.x2 - box.x1),
      height: Math.abs(box.y2 - box.y1),
    };
  });

  readonly lastPrice = computed(() => {
    const data = this.visible();
    return data.length ? data[data.length - 1].c : 0;
  });

  readonly lastColor = computed(() => {
    const data = this.visible();
    if (!data.length) {
      return '#22c55e';
    }
    const last = data[data.length - 1];
    return last.c >= last.o ? '#22c55e' : '#ef4444';
  });

  readonly lastPriceY = computed(() => {
    const range = this.max() - this.min() || 1;
    const bottom = this.height - this.pad - this.volumeHeight;
    return this.pad + ((this.max() - this.lastPrice()) / range) * (bottom - this.pad);
  });

  readonly lastPriceTop = computed(() => (this.lastPriceY() / this.height) * 100);

  zoomIn(): void {
    const data = this.candles();
    if (!data.length) {
      return;
    }
    const selected = this.range();
    if (selected) {
      const count = selected.end - selected.start + 1;
      if (count <= 8) {
        return;
      }
      const nextCount = Math.max(8, Math.ceil(count / 2));
      const center = (selected.start + selected.end) / 2;
      const start = Math.max(0, Math.min(data.length - nextCount, Math.round(center - nextCount / 2)));
      this.range.set({ start, end: start + nextCount - 1 });
      this.yDomain.set(null);
      return;
    }
    this.zoom.update((value) => Math.min(16, value + 1));
  }

  zoomOut(): void {
    const data = this.candles();
    if (!data.length) {
      return;
    }
    const selected = this.range();
    if (selected) {
      const count = selected.end - selected.start + 1;
      const nextCount = Math.min(data.length, Math.ceil(count * 2));
      if (nextCount >= data.length) {
        this.range.set(null);
      } else {
        const center = (selected.start + selected.end) / 2;
        const start = Math.max(
          0,
          Math.min(data.length - nextCount, Math.round(center - nextCount / 2)),
        );
        this.range.set({ start, end: start + nextCount - 1 });
      }
      this.yDomain.set(null);
      return;
    }
    this.zoom.update((value) => Math.max(1, value - 1));
  }

  resetZoom(): void {
    this.zoom.set(1);
    this.range.set(null);
    this.yDomain.set(null);
    this.drag.set(null);
  }

  onWheel(event: WheelEvent): void {
    if (!event.deltaY) {
      return;
    }
    event.preventDefault();
    if (event.deltaY < 0) {
      this.zoomIn();
    } else {
      this.zoomOut();
    }
  }

  onPointerDown(event: PointerEvent): void {
    if (event.button !== 0 || !this.visible().length) {
      return;
    }
    const point = this.chartPoint(event);
    this.drag.set({ x1: point.x, y1: point.y, x2: point.x, y2: point.y });
    const target = event.currentTarget as Element | null;
    target?.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  onPointerMove(event: PointerEvent): void {
    const box = this.drag();
    if (!box) {
      return;
    }
    const point = this.chartPoint(event);
    this.drag.set({ ...box, x2: point.x, y2: point.y });
    event.preventDefault();
  }

  onPointerUp(event: PointerEvent): void {
    const box = this.drag();
    if (!box) {
      return;
    }
    const point = this.chartPoint(event);
    this.drag.set(null);
    const target = event.currentTarget as Element | null;
    target?.releasePointerCapture?.(event.pointerId);
    this.applyBox({ ...box, x2: point.x, y2: point.y });
    event.preventDefault();
  }

  onPointerCancel(): void {
    this.drag.set(null);
  }

  private applyBox(box: DragBox): void {
    const base = this.visible();
    if (!base.length) {
      return;
    }
    const x1 = Math.max(this.pad, Math.min(this.width - this.pad, box.x1));
    const x2 = Math.max(this.pad, Math.min(this.width - this.pad, box.x2));
    const bottom = this.height - this.pad - this.volumeHeight;
    const y1 = Math.max(this.pad, Math.min(bottom, box.y1));
    const y2 = Math.max(this.pad, Math.min(bottom, box.y2));
    if (Math.abs(x2 - x1) < 8 || Math.abs(y2 - y1) < 8) {
      return;
    }

    const step = (this.width - this.pad * 2) / base.length;
    const first = Math.floor((Math.min(x1, x2) - this.pad) / step);
    const last = Math.floor((Math.max(x1, x2) - this.pad) / step);
    const start = Math.max(0, Math.min(base.length - 1, Math.min(first, last)));
    const end = Math.max(0, Math.min(base.length - 1, Math.max(first, last)));
    if (end - start < 1) {
      return;
    }

    const domainMax = this.max();
    const domainMin = this.min();
    const priceAt = (y: number) =>
      domainMax - ((y - this.pad) / (bottom - this.pad)) * (domainMax - domainMin);
    const low = Math.min(priceAt(y1), priceAt(y2));
    const high = Math.max(priceAt(y1), priceAt(y2));
    const padding = (high - low) * 0.03 || 1;

    const baseStart = this.visibleStart();
    this.range.set({ start: baseStart + start, end: baseStart + end });
    this.yDomain.set({ min: low - padding, max: high + padding });
  }

  private chartPoint(event: PointerEvent): { x: number; y: number } {
    const svg = event.currentTarget as SVGSVGElement;
    const rect = svg.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * this.width,
      y: ((event.clientY - rect.top) / rect.height) * this.height,
    };
  }

  private formatTime(timestamp: number): string {
    const ms = timestamp > 1e12 ? timestamp : timestamp * 1000;
    return this.timeFormatter().format(new Date(ms));
  }
}
