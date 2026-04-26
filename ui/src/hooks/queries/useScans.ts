import { useQuery } from '@tanstack/react-query';
import { getScans, getScan } from '../../api/scans';

export function useScans(params?: { thread_id?: number; limit?: number }) {
  return useQuery({
    queryKey: ['scans', params],
    queryFn: () => getScans(params),
    refetchInterval: 5000, // Poll every 5 seconds for scan status
  });
}

export function useScan(id: number) {
  return useQuery({
    queryKey: ['scans', id],
    queryFn: () => getScan(id),
    enabled: !!id,
  });
}
