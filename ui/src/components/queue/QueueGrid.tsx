import { useQueue } from '../../hooks/business/useQueue';
import { ItemCard, ItemCardSkeleton } from './ItemCard';
import { Button } from '../ui/button';
import { Select } from '../ui/select';
import { useThreads } from '../../hooks/queries/useThreads';
import { useSettings } from '../../hooks/queries/useSettings';
import { useStartScan } from '../../hooks/mutations/useStartScan';
import { ScanModal } from '../modals/ScanModal';
import { useState, useEffect, useRef } from 'react';
import { Item } from '../../types/api';

interface QueueGridProps {
  threadId: number;
}

export function QueueGrid({ threadId }: QueueGridProps) {
  const { data: settings } = useSettings();
  const settingsSort = settings?.find(s => s.key === 'sort_order')?.value as 'sent_at_desc' | 'sent_at_asc' || 'sent_at_desc';
  const userChangedSortRef = useRef(false);

  const [filters, setFilters] = useState({
    watched: undefined as boolean | undefined,
    item_type: undefined as 'reel' | 'post' | 'carousel' | 'story' | undefined,
    sort: settingsSort,
  });

  // Apply settings sort on first load only if user hasn't manually changed
  useEffect(() => {
    if (settings && !userChangedSortRef.current) {
      setFilters(prev => ({ ...prev, sort: settingsSort }));
    }
  }, [settings, settingsSort]);

  const [offset, setOffset] = useState(0);
  const [allItems, setAllItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isScanningNow, setIsScanningNow] = useState(false);

  const { data: queue, isLoading, error, refetch } = useQueue(threadId, offset, filters);
  const { mutate: startScan } = useStartScan();
  const { data: threads } = useThreads();

  const thread = threads?.find(t => t.id === threadId);

  // Reset pagination when threadId or filters change
  useEffect(() => {
    setOffset(0);
    setAllItems([]);
    setTotal(0);
  }, [threadId, filters.watched, filters.item_type, filters.sort]);

  // Accumulate items when queue data arrives
  useEffect(() => {
    if (queue) {
      setTotal(queue.total);
      if (offset === 0) {
        setAllItems(queue.items);
      } else {
        setAllItems(prev => [...prev, ...queue.items]);
      }
      setIsLoadingMore(false);
    }
  }, [queue, offset]);

  const hasMore = allItems.length < total;

  const handleScanNowInternal = () => {
    if (!thread) return;

    setIsScanningNow(true);

    startScan(
      { thread_url: thread.thread_url, max_messages: 200 },
      {
        onSuccess: () => {
          setIsScanningNow(false);
          setOffset(0);
          refetch();
        },
        onError: (error) => {
          setIsScanningNow(false);
          if (error.message.includes('Scan already in progress')) {
            // Toast already shown by mutation error handling
          }
        },
      }
    );
  };

  const handleLoadMore = () => {
    setIsLoadingMore(true);
    setOffset(prev => prev + 24);
  };

  const handleSortChange = (value: string) => {
    userChangedSortRef.current = true;
    setFilters({ ...filters, sort: value as 'sent_at_desc' | 'sent_at_asc' });
  };

  if (isLoading && offset === 0) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <ItemCardSkeleton count={8} />
      </div>
    );
  }

  if (error && offset === 0) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-semibold text-ig-text">Failed to load items</div>
          <div className="mt-2 text-ig-muted">Please try again later</div>
        </div>
      </div>
    );
  }

  if (allItems.length === 0 && !isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-semibold text-ig-text">No items found</div>
          <div className="mt-2 text-ig-muted">Try adjusting your filters</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ig-text">{thread?.display_name}</h1>
          <div className="text-ig-muted">
            @{thread?.participant_handle} • {total} items • {thread?.unwatched_count} unwatched
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Sort toggle */}
          <Select
            value={filters.sort}
            onChange={(e) => handleSortChange(e.target.value)}
          >
            <option value="sent_at_desc">Newest first</option>
            <option value="sent_at_asc">Oldest first</option>
          </Select>

          {/* Watched filter */}
          <Select
            value={filters.watched === undefined ? 'all' : filters.watched ? 'watched' : 'unwatched'}
            onChange={(e) => {
              const value = e.target.value;
              setFilters({
                ...filters,
                watched: value === 'all' ? undefined : value === 'watched',
              });
            }}
          >
            <option value="all">All items</option>
            <option value="unwatched">Unwatched only</option>
            <option value="watched">Watched</option>
          </Select>

          {/* Type filter */}
          <Select
            value={filters.item_type || 'all'}
            onChange={(e) => {
              const value = e.target.value;
              setFilters({
                ...filters,
                item_type: value === 'all' ? undefined : value as 'reel' | 'post' | 'carousel' | 'story',
              });
            }}
          >
            <option value="all">All types</option>
            <option value="reel">Reels only</option>
            <option value="post">Posts only</option>
            <option value="carousel">Carousels only</option>
            <option value="story">Stories only</option>
          </Select>

          {/* Scan now button */}
          <Button onClick={handleScanNowInternal}>
            Scan now
          </Button>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {allItems.map((item) => (
          <ItemCard key={item.id} item={item} />
        ))}
        {(isLoading || isLoadingMore) && <ItemCardSkeleton count={4} />}
      </div>

      {/* Load more */}
      {hasMore && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={handleLoadMore} disabled={isLoadingMore}>
            {isLoadingMore ? 'Loading...' : 'Load more'}
          </Button>
        </div>
      )}

      {/* Scan modal */}
      <ScanModal open={isScanningNow} />
    </div>
  );
}
