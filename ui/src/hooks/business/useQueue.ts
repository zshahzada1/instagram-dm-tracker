import { useQuery } from '@tanstack/react-query';
import { getItems } from '../../api/items';

export interface QueueFilters {
  watched?: boolean;
  item_type?: 'reel' | 'post' | 'carousel' | 'story';
  sort?: 'sent_at_desc' | 'sent_at_asc';
}

export function useQueue(threadId: number, offset: number, filters: QueueFilters = {}) {
  return useQuery({
    queryKey: ['queue', threadId, offset, filters],
    queryFn: () =>
      getItems({
        thread_id: threadId,
        sender: 'her',
        limit: 24,
        offset,
        ...filters,
      }),
  });
}
