import { apiRequest, getApiUrl } from './client';
import { Thread } from '../types/api';

export async function getThreads(): Promise<Thread[]> {
  return apiRequest<Thread[]>('/threads');
}

export async function getThread(id: number): Promise<Thread> {
  return apiRequest<Thread>(`/threads/${id}`);
}

export function getThumbnailUrl(itemId: number): string {
  return getApiUrl(`/items/${itemId}/thumbnail`);
}
