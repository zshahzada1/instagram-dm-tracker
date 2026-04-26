import { useQuery } from '@tanstack/react-query';
import { getItems, getItem } from '../../api/items';

export function useNextUnwatchedItem(
  threadId: number,
  currentItemId: number,
  filters?: {
    item_type?: 'reel' | 'post' | 'carousel' | 'story';
    sort?: 'sent_at_desc' | 'sent_at_asc';
  }
) {
  return useQuery({
    queryKey: ['next-unwatched', threadId, currentItemId, filters],
    queryFn: async () => {
      const response = await getItems({
        thread_id: threadId,
        watched: false,
        sender: 'her',
        limit: 50,
        ...filters,
      });

      // Find the next unwatched item after the current one
      const currentIndex = response.items.findIndex(item => item.id === currentItemId);
      const nextItem = response.items.slice(currentIndex + 1).find(item => !item.watched);

      return nextItem;
    },
    enabled: !!threadId && !!currentItemId,
  });
}

export function usePlayerItem(itemId: number) {
  return useQuery({
    queryKey: ['player-item', itemId],
    queryFn: () => getItem(itemId),
    enabled: !!itemId,
  });
}
