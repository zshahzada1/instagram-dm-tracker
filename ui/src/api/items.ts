import { apiRequest, getApiUrl } from './client';
import { Item, ItemsListResponse, ItemWatchedUpdate } from '../types/api';

export interface ItemsParams {
  thread_id?: number;
  watched?: boolean;
  item_type?: 'reel' | 'post' | 'carousel' | 'story';
  sender?: 'me' | 'her' | 'all';
  sort?: 'sent_at_desc' | 'sent_at_asc' | 'first_seen_desc';
  limit?: number;
  offset?: number;
}

export async function getItems(params: ItemsParams = {}): Promise<ItemsListResponse> {
  const searchParams = new URLSearchParams();

  if (params.thread_id !== undefined) searchParams.append('thread_id', String(params.thread_id));
  if (params.watched !== undefined) searchParams.append('watched', String(params.watched));
  if (params.item_type) searchParams.append('item_type', params.item_type);
  if (params.sender) searchParams.append('sender', params.sender);
  if (params.sort) searchParams.append('sort', params.sort);
  if (params.limit) searchParams.append('limit', String(params.limit));
  if (params.offset !== undefined) searchParams.append('offset', String(params.offset));

  const query = searchParams.toString();
  return apiRequest<ItemsListResponse>(`/items${query ? `?${query}` : ''}`);
}

export async function getItem(id: number): Promise<Item> {
  return apiRequest<Item>(`/items/${id}`);
}

export async function updateItemWatched(id: number, data: ItemWatchedUpdate): Promise<Item> {
  return apiRequest<Item>(`/items/${id}/watched`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function getItemThumbnailUrl(id: number): string {
  return getApiUrl(`/items/${id}/thumbnail`);
}
