import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateSetting } from '../../api/settings';
import { Setting } from '../../types/api';

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      updateSetting(key, { value }),
    onSuccess: () => {
      // Invalidate settings query
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });
}
