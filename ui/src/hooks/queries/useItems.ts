import { useQuery } from '@tanstack/react-query';
import { getItems, getItem } from '../../api/items';
import { ItemsParams } from '../../types/api';

export function useItems(params?: ItemsParams) {
  return useQuery({
    queryKey: ['items', params],
    queryFn: () => getItems(params),
  });
}

export function useItem(id: number) {
  return useQuery({
    queryKey: ['items', id],
    queryFn: () => getItem(id),
    enabled: !!id,
  });
}
