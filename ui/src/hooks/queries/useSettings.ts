import { useQuery } from '@tanstack/react-query';
import { getSettings } from '../../api/settings';
import { Setting } from '../../types/api';

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60000, // 1 minute
  });
}
