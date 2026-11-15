import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ChatEvent, ChatMessage } from '../models';
import { I18nService } from '../i18n/i18n.service';
import { ApiService } from './api.service';
import { eventToMessage } from './chat-events';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly api = inject(ApiService);
  private readonly i18n = inject(I18nService);

  readonly messages = signal<ChatMessage[]>([]);
  readonly status = signal<'idle' | 'connecting' | 'open' | 'closed'>('idle');
  readonly running = signal(false);
  readonly sessionId = signal<string | null>(null);

  private socket?: WebSocket;
  private counter = 0;
  private manualClose = false;
  private retry = 0;
  private reconnectTimer?: ReturnType<typeof setTimeout>;

  async connect(): Promise<void> {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }
    this.manualClose = false;
    this.status.set('connecting');
    let sessionId = this.sessionId();
    if (!sessionId) {
      try {
        const session = await firstValueFrom(this.api.createSession());
        sessionId = session?.session_id ?? null;
      } catch {
        sessionId = null;
      }
      if (!sessionId) {
        this.push('error', this.i18n.t('chat.error.session'));
        this.status.set('closed');
        this.scheduleReconnect();
        return;
      }
      this.sessionId.set(sessionId);
    }

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${location.host}/ws/chat/${sessionId}`);
    this.socket = socket;

    socket.onopen = () => {
      this.retry = 0;
      this.status.set('open');
    };
    socket.onclose = () => {
      this.socket = undefined;
      if (this.manualClose) {
        this.status.set('idle');
        return;
      }
      this.status.set('closed');
      if (this.running()) {
        this.running.set(false);
        this.push('error', this.i18n.t('chat.error.closed'));
      }
      this.scheduleReconnect();
    };
    socket.onerror = () => {
      if (this.status() !== 'closed') {
        this.push('error', this.i18n.t('chat.error.socket'));
      }
    };
    socket.onmessage = (message) => {
      try {
        this.handle(JSON.parse(message.data) as ChatEvent);
      } catch {
        this.push('error', this.i18n.t('chat.error.unreadable'));
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.manualClose || this.reconnectTimer) {
      return;
    }
    const delay = Math.min(1000 * 2 ** this.retry, 10_000);
    this.retry += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      void this.connect();
    }, delay);
  }

  send(text: string): boolean {
    const trimmed = text.trim();
    if (!trimmed || this.running()) {
      return false;
    }
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.push('error', this.i18n.t('chat.error.notConnected'));
      return false;
    }
    this.push('user', trimmed);
    this.running.set(true);
    this.socket.send(JSON.stringify({ message: trimmed, language: this.i18n.locale() }));
    return true;
  }

  reset(): void {
    this.manualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    this.socket?.close();
    this.socket = undefined;
    this.sessionId.set(null);
    this.messages.set([]);
    this.running.set(false);
    this.status.set('idle');
  }

  clear(): void {
    const socket = this.socket;
    this.socket = undefined;
    if (socket) {
      socket.onopen = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;
      try {
        socket.close();
      } catch {
        // The socket may already be closed; a new one is opened below.
      }
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    this.manualClose = false;
    this.retry = 0;
    this.sessionId.set(null);
    this.messages.set([]);
    this.running.set(false);
    this.status.set('idle');
    void this.connect();
  }

  private handle(event: ChatEvent): void {
    switch (event.type) {
      case 'Ready':
        this.status.set('open');
        return;
      case 'AgentErrorEvent':
      case 'Error':
        this.running.set(false);
        break;
      case 'Done':
        this.running.set(false);
        return;
      default:
        break;
    }
    const message = eventToMessage(event, this.counter++, (key) => this.i18n.t(key));
    if (message) {
      this.messages.update((current) => [...current, message]);
    }
  }

  private push(
    role: ChatMessage['role'],
    text: string,
    tool?: string,
    extra?: Partial<ChatMessage>,
  ): void {
    const message: ChatMessage = {
      id: `m${this.counter++}`,
      role,
      text,
      tool,
      time: Date.now(),
      ...extra,
    };
    this.messages.update((current) => [...current, message]);
  }
}
