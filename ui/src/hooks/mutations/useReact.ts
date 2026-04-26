import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendReaction, ReactRequest, ReactResponse } from '../../api/reactor';

export function useReact() {
  const queryClient = useQueryClient();

  return useMutation<ReactResponse, Error, ReactRequest>({
    mutationFn: (data: ReactRequest) => sendReaction(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['threads'] });
    },
  });
}
