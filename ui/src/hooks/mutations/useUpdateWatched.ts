import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateItemWatched } from '../../api/items';
import { Item } from '../../types/api';

export function useUpdateWatched() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, watched }: { id: number; watched: boolean }) =>
      updateItemWatched(id, { watched }),
    onSuccess: (data: Item) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['threads'] });
    },
  });
}
