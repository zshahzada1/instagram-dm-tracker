import { useQuery } from '@tanstack/react-query';
import { getThreads, getThread } from '../../api/threads';

export function useThreads() {
  return useQuery({
    queryKey: ['threads'],
    queryFn: getThreads,
    staleTime: 30000, // 30 seconds
  });
}

export function useThread(id: number) {
  return useQuery({
    queryKey: ['threads', id],
    queryFn: () => getThread(id),
    enabled: !!id,
  });
}
