import { apiRequest } from './client';
import { ScanStartRequest, ScanResponse, ScanRun } from '../types/api';

export async function startScan(data: ScanStartRequest): Promise<ScanResponse> {
  return apiRequest<ScanResponse>('/scans', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getScans(params: { thread_id?: number; limit?: number } = {}): Promise<ScanRun[]> {
  const searchParams = new URLSearchParams();

  if (params.thread_id !== undefined) searchParams.append('thread_id', String(params.thread_id));
  if (params.limit) searchParams.append('limit', String(params.limit));

  const query = searchParams.toString();
  return apiRequest<ScanRun[]>(`/scans${query ? `?${query}` : ''}`);
}

export async function getScan(id: number): Promise<ScanRun> {
  return apiRequest<ScanRun>(`/scans/${id}`);
}
