import { apiRequest } from './client';
import { Setting, SettingUpdate } from '../types/api';

export async function getSettings(): Promise<Setting[]> {
  return apiRequest<Setting[]>('/settings');
}

export async function updateSetting(key: string, data: SettingUpdate): Promise<Setting> {
  return apiRequest<Setting>(`/settings/${key}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}
