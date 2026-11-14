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

  async connect(): Promise<void> {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }
    this.status.set('connecting');
    let sessionId = this.sessionId();
    if (!sessionId) {
      const session = await firstValueFrom(this.api.createSession());
      sessionId = session?.session_id ?? null;
      if (!sessionId) {
        this.push('error', 'Could not create a chat session.');
        this.status.set('closed');
        return;
      }
      this.sessionId.set(sessionId);
    }

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${location.host}/ws/chat/${sessionId}`);
    this.socket = socket;

    socket.onopen = () => this.status.set('open');
    socket.onclose = () => this.status.set('closed');
    socket.onerror = () => this.push('error', 'WebSocket connection error.');
    socket.onmessage = (message) => {
      try {
        this.handle(JSON.parse(message.data) as ChatEvent);
      } catch {
        this.push('error', 'Received an unreadable event from the server.');
      }
    };
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
        const detail = event.thought?.trim() || this.describeAction(event.action);
        this.push('tool', detail, event.tool_name);
        break;
      }
      case 'ObservationEvent': {
        const text = (event.observation ?? '').trim();
        const clipped = text.length > 1500 ? `${text.slice(0, 1500)}…` : text;
        this.push('tool', clipped || '(empty result)', `${event.tool_name} result`);
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

  private describeAction(action: unknown): string {
    if (!action) {
      return 'Calling tool…';
    }
    try {
      const text = JSON.stringify(action);
      return text.length > 500 ? `${text.slice(0, 500)}…` : text;
    } catch {
      return 'Calling tool…';
    }
  }

  private push(role: ChatMessage['role'], text: string, tool?: string): void {
    const message: ChatMessage = {
      id: `m${this.counter++}`,
      role,
      text,
      tool,
      time: Date.now(),
    };
    this.messages.update((current) => [...current, message]);
  }
}
