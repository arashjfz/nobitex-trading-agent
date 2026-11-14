import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-chat-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  template: `
    <section class="chat">
      <header>
        <div>
          <h2>Agent chat</h2>
          <p class="hint">Ask for opportunities, analysis, or place an order.</p>
        </div>
        <span class="status" [class.open]="chat.status() === 'open'">{{ chat.status() }}</span>
      </header>

      <div class="messages" #scroller>
        @if (chat.messages().length === 0) {
          <div class="suggestions">
            <button type="button" (click)="use('Find the best crypto opportunity right now')">
              Find the best opportunity
            </button>
            <button type="button" (click)="use('Analyze BTCUSDT on the 1h timeframe')">
              Analyze BTCUSDT
            </button>
            <button type="button" (click)="use('Show my wallet balances')">
              Show balances
            </button>
          </div>
        }
        @for (message of chat.messages(); track message.id) {
          <article class="msg" [class]="message.role">
            <div class="meta">
              <span class="who">{{ label(message.role) }}</span>
              @if (message.tool) {
                <span class="tool">{{ message.tool }}</span>
              }
            </div>
            <pre>{{ message.text }}</pre>
          </article>
        }
        @if (chat.running()) {
          <p class="thinking">Nobi is working…</p>
        }
      </div>

      <form (submit)="submit($event)">
        <textarea
          [(ngModel)]="draft"
          name="draft"
          rows="2"
          placeholder="e.g. Buy 0.001 BTCUSDT at market if the 1h signal is BUY"
          (keydown.enter)="onEnter($event)"
        ></textarea>
        <button type="submit" [disabled]="chat.running() || !draft().trim()">Send</button>
      </form>
    </section>
  `,
  styles: [
    `
      .chat {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 420px;
      }
      header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
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
      .status {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 3px 8px;
        border-radius: 999px;
        background: #1e293b;
        color: #94a3b8;
      }
      .status.open {
        background: #052e1a;
        color: #4ade80;
      }
      .messages {
        flex: 1;
        overflow-y: auto;
        margin: 10px 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-right: 4px;
      }
      .suggestions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .suggestions button {
        background: #111c2e;
        border: 1px solid #1e293b;
        color: #cbd5e1;
        font-size: 11px;
        padding: 6px 10px;
        border-radius: 999px;
        cursor: pointer;
      }
      .suggestions button:hover {
        border-color: #38bdf8;
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
      .meta {
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
      form {
        display: flex;
        gap: 8px;
        align-items: flex-end;
      }
      textarea {
        flex: 1;
        resize: none;
        background: #0b1220;
        border: 1px solid #1e293b;
        border-radius: 8px;
        color: #e2e8f0;
        padding: 8px 10px;
        font-family: inherit;
        font-size: 12.5px;
      }
      textarea:focus {
        outline: none;
        border-color: #38bdf8;
      }
      form button {
        background: #0284c7;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: 600;
        cursor: pointer;
      }
      form button:disabled {
        background: #1e293b;
        color: #64748b;
        cursor: not-allowed;
      }
    `,
  ],
})
export class ChatPanelComponent {
  readonly chat = inject(ChatService);
  readonly draft = signal('');
  private readonly scroller = viewChild<ElementRef<HTMLDivElement>>('scroller');

  constructor() {
    void this.chat.connect();
    effect(() => {
      this.chat.messages();
      queueMicrotask(() => {
        const element = this.scroller()?.nativeElement;
        if (element) {
          element.scrollTop = element.scrollHeight;
        }
      });
    });
  }

  label(role: string): string {
    switch (role) {
      case 'user':
        return 'You';
      case 'assistant':
        return 'Nobi';
      case 'tool':
        return 'Tool';
      case 'error':
        return 'Error';
      default:
        return 'System';
    }
  }

  use(text: string): void {
    this.draft.set(text);
  }

  submit(event: Event): void {
    event.preventDefault();
    if (this.chat.send(this.draft())) {
      this.draft.set('');
    }
  }

  onEnter(event: Event): void {
    const keyboard = event as KeyboardEvent;
    if (!keyboard.shiftKey) {
      event.preventDefault();
      if (this.chat.send(this.draft())) {
        this.draft.set('');
      }
    }
  }
}
