import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ChatEvent, ChatMessage } from '../models';
import { ApiService } from './api.service';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly api = inject(ApiService);

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
        this.push('error', 'Could not create a chat session. Is the backend running?');
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
        this.push('error', 'Connection closed before the agent finished. Reconnecting…');
      }
      this.scheduleReconnect();
    };
    socket.onerror = () => {
      if (this.status() !== 'closed') {
        this.push('error', 'WebSocket connection error.');
      }
    };
    socket.onmessage = (message) => {
      try {
        this.handle(JSON.parse(message.data) as ChatEvent);
      } catch {
        this.push('error', 'Received an unreadable event from the server.');
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
      this.push('error', 'Chat is not connected yet. Please wait a moment and retry.');
      return false;
    }
    this.push('user', trimmed);
    this.running.set(true);
    this.socket.send(JSON.stringify({ message: trimmed }));
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

  private handle(event: ChatEvent): void {
    switch (event.type) {
      case 'Ready':
        this.status.set('open');
        break;
      case 'MessageEvent':
        if (event.source === 'user') {
          return;
        }
        if (event.text?.trim()) {
          this.push('assistant', event.text.trim());
        }
        break;
      case 'ActionEvent': {
        this.push('tool', event.thought?.trim() ?? '', event.tool_name, {
          kind: 'action',
          args: this.actionArgs(event.action),
        });
        break;
      }
      case 'ObservationEvent': {
        const parsed = this.parseObservation(event.observation);
        this.push('tool', parsed.text, event.tool_name, {
          kind: 'observation',
          data: event.data ?? parsed.data,
          failed: event.is_error,
        });
        break;
      }
      case 'AgentErrorEvent':
      case 'Error':
        this.push('error', event.error ?? 'The agent reported an error.');
        this.running.set(false);
        break;
      case 'Done':
        this.running.set(false);
        break;
      default:
        break;
    }
  }

  private actionArgs(action: unknown): Record<string, unknown> | undefined {
    if (!action || typeof action !== 'object' || Array.isArray(action)) {
      return undefined;
    }
    const raw = { ...(action as Record<string, unknown>) };
    delete raw['kind'];
    const data = raw['data'];
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      delete raw['data'];
      return { ...raw, ...(data as Record<string, unknown>) };
    }
    return raw;
  }

  private parseObservation(observation: string | undefined): {
    text: string;
    data?: unknown;
  } {
    let text = (observation ?? '').trim();
    const prefix = /^\[Tool '[^']+' executed\.\]\s*/;
    text = text.replace(prefix, '');
    if (!text) {
      return { text: '' };
    }
    if (text.startsWith('{') || text.startsWith('[')) {
      try {
        return { text, data: JSON.parse(text) };
      } catch {
        return { text };
      }
    }
    return { text };
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
