import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CronPreview, ScheduledTask } from '../../models';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-schedule-panel',
  imports: [FormsModule, DatePipe],
  template: `
    <section class="scheduler">
      <header>
        <h2>Schedule</h2>
        <span class="tz">{{ timezone() }}</span>
      </header>

      <div class="form">
        <label>
          Name (optional)
          <input [(ngModel)]="name" name="name" placeholder="Morning scan" />
        </label>

        <label>
          Prompt
          <textarea
            [(ngModel)]="prompt"
            name="prompt"
            rows="3"
            placeholder="Find the best opportunities and buy or sell up to 50 dollars."
          ></textarea>
        </label>

        <label>
          Cron
          <input
            [(ngModel)]="cron"
            name="cron"
            (ngModelChange)="onCronChange($event)"
            placeholder="0 9 * * *"
          />
        </label>

        <div class="presets">
          @for (preset of presets; track preset.cron) {
            <button type="button" (click)="usePreset(preset.cron)">{{ preset.label }}</button>
          }
        </div>

        @if (preview(); as p) {
          @if (p.valid) {
            <p class="hint">
              Next:
              @for (run of p.next_runs; track run) {
                <span>{{ run | date: 'short' }}</span>
              }
            </p>
          } @else {
            <p class="err">{{ p.error }}</p>
          }
        }

        <button
          class="primary"
          type="button"
          (click)="create()"
          [disabled]="saving() || !prompt.trim() || !cron.trim()"
        >
          {{ saving() ? 'Scheduling…' : 'Schedule task' }}
        </button>

        @if (error()) {
          <pre class="err">{{ error() }}</pre>
        }
      </div>

      <div class="tasks">
        @if (tasks().length === 0) {
          <p class="empty">No scheduled tasks yet.</p>
        }
        @for (task of tasks(); track task.id) {
          <article class="task" [class.off]="!task.enabled">
            <div class="row">
              <strong>{{ task.name }}</strong>
              <code>{{ task.cron }}</code>
            </div>
            <p class="prompt">{{ task.prompt }}</p>
            <p class="meta">
              next {{ task.next_run ? (task.next_run | date: 'short') : 'paused' }}
              · runs {{ task.run_count }}
              @if (task.last_status) {
                · last {{ task.last_status }}
              }
            </p>
            @if (task.last_result) {
              <details>
                <summary>Last result</summary>
                <pre>{{ task.last_result }}</pre>
              </details>
            }
            <div class="actions">
              <button type="button" (click)="toggle(task)">
                {{ task.enabled ? 'Pause' : 'Resume' }}
              </button>
              <button type="button" (click)="runNow(task)">Run now</button>
              <button type="button" class="danger" (click)="remove(task)">Delete</button>
            </div>
          </article>
        }
      </div>
    </section>
  `,
  styles: [
    `
      .scheduler {
        display: flex;
        flex-direction: column;
        gap: 14px;
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
      .tz {
        font-size: 10px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      .form {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      label {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8;
      }
      input,
      textarea {
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 8px;
        color: #e2e8f0;
        padding: 8px 10px;
        font-size: 12px;
        font-family: inherit;
        resize: vertical;
      }
      input:focus,
      textarea:focus {
        outline: none;
        border-color: #38bdf8;
      }
      .presets {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .presets button,
      .actions button {
        background: #111c2e;
        border: 1px solid #1e293b;
        color: #cbd5e1;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 10px;
        cursor: pointer;
      }
      .presets button:hover,
      .actions button:hover {
        border-color: #38bdf8;
      }
      .primary {
        background: #0ea5e9;
        border: none;
        color: #04121f;
        font-weight: 700;
        border-radius: 8px;
        padding: 9px 12px;
        cursor: pointer;
      }
      .primary:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .hint {
        margin: 0;
        font-size: 10px;
        color: #7dd3fc;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .hint span + span::before {
        content: ' · ';
        color: #475569;
      }
      .err {
        margin: 0;
        font-size: 11px;
        color: #fca5a5;
        white-space: pre-wrap;
      }
      .empty {
        margin: 0;
        font-size: 12px;
        color: #64748b;
      }
      .tasks {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .task {
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        background: #0b1220;
      }
      .task.off {
        opacity: 0.55;
      }
      .row {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        align-items: baseline;
      }
      .row strong {
        font-size: 12px;
      }
      code {
        font-size: 10px;
        color: #7dd3fc;
        background: #0f1b2d;
        padding: 2px 6px;
        border-radius: 4px;
      }
      .prompt {
        margin: 0;
        font-size: 11px;
        color: #cbd5e1;
        line-height: 1.4;
      }
      .meta {
        margin: 0;
        font-size: 10px;
        color: #64748b;
      }
      details {
        font-size: 10px;
        color: #94a3b8;
      }
      details pre {
        margin: 4px 0 0;
        white-space: pre-wrap;
        max-height: 140px;
        overflow: auto;
        color: #cbd5e1;
      }
      .actions {
        display: flex;
        gap: 6px;
      }
      .danger {
        color: #fca5a5;
        border-color: #7f1d1d;
      }
    `,
  ],
})
export class SchedulePanelComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  readonly tasks = signal<ScheduledTask[]>([]);
  readonly timezone = signal('');
  readonly preview = signal<CronPreview | null>(null);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  name = '';
  prompt = '';
  cron = '0 9 * * *';

  readonly presets = [
    { label: 'Every 15 min', cron: '*/15 * * * *' },
    { label: 'Hourly', cron: '0 * * * *' },
    { label: 'Daily 09:00', cron: '0 9 * * *' },
    { label: 'Weekdays 09:00', cron: '0 9 * * 1-5' },
    { label: 'Weekly Mon 09:00', cron: '0 9 * * 1' },
  ];

  private refreshTimer?: ReturnType<typeof setInterval>;
  private cronTimer?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.load();
    this.refreshTimer = setInterval(() => this.load(), 30_000);
  }

  ngOnDestroy(): void {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    if (this.cronTimer) clearTimeout(this.cronTimer);
  }

  load(): void {
    this.api.schedules().subscribe({
      next: (result) => {
        this.timezone.set(result.timezone);
        this.tasks.set(result.tasks);
      },
      error: () => undefined,
    });
  }

  onCronChange(value: string): void {
    if (this.cronTimer) clearTimeout(this.cronTimer);
    this.cronTimer = setTimeout(() => this.validate(value), 350);
  }

  validate(value: string): void {
    if (!value.trim()) {
      this.preview.set(null);
      return;
    }
    this.api.validateCron(value).subscribe({
      next: (result) => this.preview.set(result),
      error: () => this.preview.set(null),
    });
  }

  usePreset(cron: string): void {
    this.cron = cron;
    this.validate(cron);
  }

  create(): void {
    this.error.set(null);
    this.saving.set(true);
    this.api
      .createSchedule({
        name: this.name.trim() || undefined,
        prompt: this.prompt.trim(),
        cron: this.cron.trim(),
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.name = '';
          this.prompt = '';
          this.load();
        },
        error: (err) => {
          this.saving.set(false);
          this.error.set(err?.error?.detail ?? 'Could not create the task');
        },
      });
  }

  toggle(task: ScheduledTask): void {
    this.api.updateSchedule(task.id, { enabled: !task.enabled }).subscribe({
      next: () => this.load(),
      error: (err) => this.error.set(err?.error?.detail ?? 'Could not update the task'),
    });
  }

  runNow(task: ScheduledTask): void {
    this.api.runSchedule(task.id).subscribe({
      next: () => setTimeout(() => this.load(), 1500),
      error: (err) => this.error.set(err?.error?.detail ?? 'Could not start the task'),
    });
  }

  remove(task: ScheduledTask): void {
    this.api.deleteSchedule(task.id).subscribe({
      next: () => this.load(),
      error: (err) => this.error.set(err?.error?.detail ?? 'Could not delete the task'),
    });
  }
}
