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
import { I18nService } from '../../i18n/i18n.service';
import { MarkdownPipe } from '../../pipes/markdown.pipe';
import { ToolViewComponent } from '../tool-view/tool-view.component';

@Component({
  selector: 'app-chat-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MarkdownPipe, ToolViewComponent],
  template: `
    <section class="chat">
      <header>
        <div>
          <h2>{{ i18n.t('chat.title') }}</h2>
          <p class="hint">{{ i18n.t('chat.hint') }}</p>
        </div>
        <div class="actions">
          <button
            type="button"
            class="clear"
            (click)="chat.clear()"
            [disabled]="chat.messages().length === 0"
            [title]="i18n.t('chat.clearHint')"
          >
            {{ i18n.t('chat.clear') }}
          </button>
          <span class="status" [class.open]="chat.status() === 'open'">
            {{ i18n.t('chat.status.' + chat.status()) }}
          </span>
        </div>
      </header>

      <div class="messages" #scroller>
        @if (chat.messages().length === 0) {
          <div class="suggestions">
            <button type="button" (click)="use(i18n.t('chat.suggestion.find'))">
              {{ i18n.t('chat.findOpportunity') }}
            </button>
            <button type="button" (click)="use(i18n.t('chat.suggestion.analyze'))">
              {{ i18n.t('chat.analyze') }}
            </button>
            <button type="button" (click)="use(i18n.t('chat.suggestion.balances'))">
              {{ i18n.t('chat.balances') }}
            </button>
          </div>
        }
        @for (message of chat.messages(); track message.id) {
          <article class="msg" [class]="message.role">
            <div class="meta">
              <span class="who">{{ label(message.role) }}</span>
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
        @if (chat.running()) {
          <p class="thinking">{{ i18n.t('chat.thinking') }}</p>
        }
      </div>

      <form (submit)="submit($event)">
        <textarea
          [(ngModel)]="draft"
          name="draft"
          rows="2"
          dir="auto"
          [placeholder]="i18n.t('chat.placeholder')"
          (keydown.enter)="onEnter($event)"
        ></textarea>
        <button type="submit" [disabled]="chat.running() || !draft().trim()">
          {{ i18n.t('chat.send') }}
        </button>
      </form>
    </section>
  `,
  styles: [
    `
      .chat {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        width: 100%;
      }
      header {
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
      .status {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 3px 8px;
        border-radius: 999px;
        background: #1e293b;
        color: #94a3b8;
      }
      .actions {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
      }
      .clear {
        background: transparent;
        border: 1px solid #1e293b;
        color: #94a3b8;
        border-radius: 6px;
        padding: 3px 8px;
        font-size: 10px;
        cursor: pointer;
      }
      .clear:hover:not(:disabled) {
        border-color: #38bdf8;
        color: #7dd3fc;
      }
      .clear:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      .status.open {
        background: #052e1a;
        color: #4ade80;
      }
      .messages {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        margin: 10px 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-inline-end: 4px;
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
        flex-shrink: 0;
        padding-top: 8px;
        border-top: 1px solid #1e293b;
        background: #0d1524;
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
  readonly i18n = inject(I18nService);
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
        return this.i18n.t('chat.you');
      case 'assistant':
        return this.i18n.t('chat.nobi');
      case 'tool':
        return this.i18n.t('chat.tool');
      case 'error':
        return this.i18n.t('chat.error');
      default:
        return this.i18n.t('chat.system');
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
