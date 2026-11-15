import { ChatEvent, ChatMessage } from '../models';

export type Translate = (key: string) => string;

function actionArgs(action: unknown): Record<string, unknown> | undefined {
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

function parseObservation(observation: string | undefined): {
  text: string;
  data?: unknown;
} {
  let text = (observation ?? '').trim();
  text = text.replace(/^\[Tool '[^']+' executed\.\]\s*/, '');
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

export function eventToMessage(
  event: ChatEvent,
  index: number,
  t: Translate,
  includeUser = false,
): ChatMessage | null {
  const id = event.id ?? `ev${index}`;
  const parsedTime = event.timestamp ? Date.parse(event.timestamp) : Number.NaN;
  const time = Number.isNaN(parsedTime) ? Date.now() : parsedTime;

  switch (event.type) {
    case 'MessageEvent': {
      if (event.source === 'user' && !includeUser) {
        return null;
      }
      const text = event.text?.trim();
      if (!text) {
        return null;
      }
      return {
        id,
        role: event.source === 'user' ? 'user' : 'assistant',
        text,
        time,
      };
    }
    case 'ActionEvent':
      return {
        id,
        role: 'tool',
        text: event.thought?.trim() ?? '',
        tool: event.tool_name,
        time,
        kind: 'action',
        args: actionArgs(event.action),
      };
    case 'ObservationEvent': {
      const parsed = parseObservation(event.observation);
      return {
        id,
        role: 'tool',
        text: parsed.text,
        tool: event.tool_name,
        time,
        kind: 'observation',
        data: event.data ?? parsed.data,
        failed: event.is_error,
      };
    }
    case 'AgentErrorEvent':
    case 'Error':
      return {
        id,
        role: 'error',
        text: event.error ?? t('chat.error.agent'),
        time,
      };
    default:
      return null;
  }
}
