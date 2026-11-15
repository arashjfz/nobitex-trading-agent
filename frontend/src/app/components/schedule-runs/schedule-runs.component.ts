import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatMessage, ScheduledRun, ScheduledRunDetail, ScheduledTask } from '../../models';
import { I18nService } from '../../i18n/i18n.service';
import { LocalDatePipe } from '../../pipes/local-date.pipe';
import { MarkdownPipe } from '../../pipes/markdown.pipe';
import { ApiService } from '../../services/api.service';
import { eventToMessage } from '../../services/chat-events';
import { ToolViewComponent } from '../tool-view/tool-view.component';

@Component({
  selector: 'app-schedule-runs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, LocalDatePipe, MarkdownPipe, ToolViewComponent],
  template: `
    <section class="runs">
      <header class="head">
        <div>
          <h2>{{ i18n.t('runs.title') }}</h2>
          <p class="hint">{{ i18n.t('runs.hint') }}</p>
        </div>
        <button type="button" class="refresh" (click)="refresh()" [disabled]="loading()">
          {{ loading() ? i18n.t('runs.loading') : i18n.t('runs.refresh') }}
        </button>
      </header>

      <label class="filter">
        {{ i18n.t('runs.filter') }}
        <select [ngModel]="filter()" (ngModelChange)="setFilter($event)" name="runFilter">
          <option value="">{{ i18n.t('runs.allTasks') }}</option>
          @for (task of tasks(); track task.id) {
            <option [value]="task.id">{{ task.name }}</option>
          }
        </select>
      </label>

      @if (error()) {
        <pre class="err">{{ error() }}</pre>
      }

      <div class="list">
        @if (runs().length === 0) {
          <p class="empty">{{ i18n.t('runs.empty') }}</p>
        }
        @for (run of runs(); track run.id) {
          <button
            type="button"
            class="run"
            [class.active]="selectedId() === run.id"
            (click)="select(run)"
          >
            <span class="row">
              <strong>{{ run.task_name }}</strong>
              <span class="status" [class]="run.status">{{ statusLabel(run.status) }}</span>
            </span>
            <span class="meta">
              {{ run.started_at | localDate: i18n.locale() }} ·
              {{ duration(run) }} · {{ triggerLabel(run.trigger) }}
            </span>
            <span class="preview" dir="auto">{{ run.result || run.prompt }}</span>
          </button>
        }
      </div>

      <div class="detail">
        @if (detail(); as run) {
          <div class="detail-head">
            <div>
              <strong>{{ run.task_name }}</strong>
              <p class="meta">
                {{ run.started_at | localDate: i18n.locale() }} ·
                {{ duration(run) }} · {{ triggerLabel(run.trigger) }} ·
                {{ i18n.t('runs.events', { count: run.event_count }) }}
              </p>
            </div>
            <span class="status" [class]="run.status">{{ statusLabel(run.status) }}</span>
          </div>

          <p class="prompt" dir="auto">
            <span class="label">{{ i18n.t('runs.prompt') }}</span>{{ run.prompt }}
          </p>

          <div class="messages">
            @if (messages().length === 0) {
              <p class="empty">{{ i18n.t('runs.noMessages') }}</p>
            }
            @for (message of messages(); track message.id) {
              <article class="msg" [class]="message.role">
                <div class="meta">
                  <span class="who">{{ roleLabel(message.role) }}</span>
                  @if (message.tool) {
                    <span class="tool">{{ message.tool }}</span>
                  }
                </div>
                @if (message.role === 'assistant') {
                  <div class="markdown" dir="auto" [innerHTML]="message.text | markdown"></div>
                } @else if (message.role === 'tool') {
                  <app-tool-view [message]="message" />
                } @else {
                  <pre dir="auto">{{ message.text }}</pre>
                }
              </article>
            }
            @if (run.status === 'running') {
              <p class="thinking">{{ i18n.t('runs.running') }}</p>
            }
          </div>
        } @else {
          <p class="empty select">{{ i18n.t('runs.select') }}</p>
        }
      </div>
    </section>
  `,
  styles: [
    `
      .runs {
        display: flex;
        flex-direction: column;
        gap: 10px;
        height: 100%;
        min-height: 0;
      }
      .head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
        flex-shrink: 0;
      }
      h2 {
        margin: 0;
        font-size: 15px;
      }
      .hint {
        margin: 2px 0 0;
        font-size: 11px;
        color: #64748b;
      }
      .refresh {
        background: #111c2e;
        border: 1px solid #1e293b;
        color: #cbd5e1;
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 10px;
        cursor: pointer;
        flex-shrink: 0;
      }
      .refresh:hover:not(:disabled) {
        border-color: #38bdf8;
      }
      .refresh:disabled {
        opacity: 0.5;
        cursor: wait;
      }
      .filter {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8;
        flex-shrink: 0;
      }
      .filter select {
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 8px;
        color: #e2e8f0;
        padding: 7px 9px;
        font-size: 12px;
        font-family: inherit;
      }
      .filter select:focus {
        outline: none;
        border-color: #38bdf8;
      }
      .list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        max-height: 190px;
        overflow-y: auto;
        padding-inline-end: 4px;
        flex-shrink: 0;
      }
      .run {
        display: flex;
        flex-direction: column;
        gap: 3px;
        text-align: start;
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 9px;
        padding: 8px 10px;
        color: inherit;
        cursor: pointer;
        font-family: inherit;
      }
      .run:hover {
        border-color: #334155;
      }
      .run.active {
        border-color: #0ea5e9;
        background: #0c1b2b;
      }
      .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .row strong {
        font-size: 12px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .meta {
        font-size: 10px;
        color: #64748b;
        margin: 0;
      }
      .preview {
        font-size: 11px;
        color: #94a3b8;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 100%;
      }
      .status {
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 2px 7px;
        border-radius: 999px;
        background: #1e293b;
        color: #94a3b8;
        flex-shrink: 0;
      }
      .status.ok {
        background: #052e1a;
        color: #4ade80;
      }
      .status.running {
        background: #082f49;
        color: #38bdf8;
      }
      .status.error,
      .status.timeout,
      .status.interrupted {
        background: #2a0f12;
        color: #fca5a5;
      }
      .detail {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        border-top: 1px solid #1e293b;
        padding-top: 10px;
      }
      .detail-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
        flex-shrink: 0;
      }
      .detail-head strong {
        font-size: 13px;
      }
      .prompt {
        margin: 0;
        font-size: 11px;
        color: #cbd5e1;
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 7px 9px;
        line-height: 1.4;
        flex-shrink: 0;
      }
      .prompt .label {
        display: block;
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        margin-bottom: 3px;
      }
      .messages {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-inline-end: 4px;
      }
      .msg {
        border-radius: 8px;
        padding: 8px 10px;
        background: #0f172a;
        border: 1px solid #1e293b;
      }
      .msg.user {
        background: #0c2438;
        border-color: #164e63;
      }
      .msg.assistant {
        background: #0f1f17;
        border-color: #14532d;
      }
      .msg.tool {
        background: #14121f;
        border-color: #312e81;
      }
      .msg.error {
        background: #2a0f12;
        border-color: #7f1d1d;
      }
      .msg .meta {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-bottom: 4px;
      }
      .who {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8;
      }
      .tool {
        font-size: 10px;
        color: #a5b4fc;
        font-family: ui-monospace, monospace;
      }
      pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: inherit;
        font-size: 12.5px;
        line-height: 1.5;
        color: #e2e8f0;
      }
      .thinking {
        font-size: 11px;
        color: #38bdf8;
        margin: 0;
      }
      .empty {
        margin: 0;
        font-size: 12px;
        color: #64748b;
      }
      .empty.select {
        margin: auto;
        text-align: center;
        padding: 20px;
      }
      .err {
        margin: 0;
        font-size: 11px;
        color: #fca5a5;
        white-space: pre-wrap;
      }
    `,
  ],
})
export class ScheduleRunsComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  readonly i18n = inject(I18nService);

  readonly taskId = input<string | null>(null);
  readonly runs = signal<ScheduledRun[]>([]);
  readonly tasks = signal<ScheduledTask[]>([]);
  readonly detail = signal<ScheduledRunDetail | null>(null);
  readonly selectedId = signal<string | null>(null);
  readonly filter = signal('');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly messages = computed<ChatMessage[]>(() => {
    const run = this.detail();
    if (!run) {
      return [];
    }
    const mapped = run.events
      .map((event, index) => eventToMessage(event, index, (key) => this.i18n.t(key), true))
      .filter((message): message is ChatMessage => message !== null);
    if (!mapped.some((message) => message.role === 'user')) {
      mapped.unshift({
        id: 'prompt',
        role: 'user',
        text: run.prompt,
        time: Date.parse(run.started_at) || Date.now(),
      });
    }
    return mapped;
  });

  private readonly timer = setInterval(() => this.refresh(), 10_000);

  constructor() {
    effect(() => {
      const id = this.taskId();
      this.filter.set(id ?? '');
      this.selectedId.set(null);
      this.detail.set(null);
      this.load();
    });
    this.loadTasks();
  }

  ngOnDestroy(): void {
    clearInterval(this.timer);
  }

  refresh(): void {
    this.load();
    const selected = this.selectedId();
    if (selected) {
      this.loadDetail(selected);
    }
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.runs(this.filter() || undefined).subscribe({
      next: (result) => {
        this.loading.set(false);
        this.runs.set(result.runs);
        const selected = this.selectedId();
        if (selected && result.runs.some((run) => run.id === selected)) {
          return;
        }
        if (result.runs.length > 0) {
          this.select(result.runs[0]);
        } else {
          this.selectedId.set(null);
          this.detail.set(null);
        }
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err?.error?.detail ?? this.i18n.t('runs.error.load'));
      },
    });
  }

  loadTasks(): void {
    this.api.schedules().subscribe({
      next: (result) => this.tasks.set(result.tasks),
      error: () => undefined,
    });
  }

  setFilter(taskId: string): void {
    this.filter.set(taskId);
    this.selectedId.set(null);
    this.detail.set(null);
    this.load();
  }

  select(run: ScheduledRun): void {
    this.selectedId.set(run.id);
    this.loadDetail(run.id);
  }

  loadDetail(id: string): void {
    this.api.runDetail(id).subscribe({
      next: (run) => {
        if (this.selectedId() === id) {
          this.detail.set(run);
        }
      },
      error: (err) => this.error.set(err?.error?.detail ?? this.i18n.t('runs.error.load')),
    });
  }

  statusLabel(status: string): string {
    return this.i18n.t(`runs.status.${status}`);
  }

  triggerLabel(trigger: string): string {
    return this.i18n.t(`runs.trigger.${trigger}`);
  }

  roleLabel(role: string): string {
    return this.i18n.t(`runs.role.${role}`);
  }

  duration(run: ScheduledRun): string {
    if (!run.finished_at) {
      return this.i18n.t('runs.running');
    }
    const seconds = Math.max(
      0,
      Math.round((Date.parse(run.finished_at) - Date.parse(run.started_at)) / 1000),
    );
    if (seconds < 60) {
      return this.i18n.t('runs.seconds', { count: seconds });
    }
    return this.i18n.t('runs.minutes', { count: Math.round(seconds / 60) });
  }
}
