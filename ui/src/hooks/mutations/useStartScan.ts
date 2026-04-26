import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startScan } from '../../api/scans';
import { ScanStartRequest } from '../../types/api';

export function useStartScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ScanStartRequest) => startScan(data),
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['threads'] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['scans'] });
    },
  });
}
