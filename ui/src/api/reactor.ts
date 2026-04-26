import { apiRequest } from './client';

export interface ReactRequest {
  item_id: number;
  emoji?: string;
  dry_run?: boolean;
}

export interface ReactResponse {
  status: string;
  emoji?: string;
  message_id?: string;
  mutation_confirmed?: boolean;
  skipped?: boolean;
  source?: string;
  reason?: string;
  item_id?: number;
  would_react_with?: string;
  poster_handle?: string;
  ig_message_id?: string;
}

export async function sendReaction(data: ReactRequest): Promise<ReactResponse> {
  return apiRequest<ReactResponse>('/reactor/react', {
    method: 'POST',
    body: JSON.stringify({
      item_id: data.item_id,
      emoji: data.emoji || '❤',
      dry_run: data.dry_run || false,
    }),
  });
}
