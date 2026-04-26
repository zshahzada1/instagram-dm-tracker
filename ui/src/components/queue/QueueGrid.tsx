import { useQueue } from '../../hooks/business/useQueue';
import { ItemCard, ItemCardSkeleton } from './ItemCard';
import { Button } from '../ui/button';
import { Select } from '../ui/select';
import { useThreads } from '../../hooks/queries/useThreads';
import { useStartScan } from '../../hooks/mutations/useStartScan';
import { useState } from 'react';

interface QueueGridProps {
  threadId: number;
}

export function QueueGrid({ threadId }: QueueGridProps) {
  const [filters, setFilters] = useState({
    watched: undefined as boolean | undefined,
    item_type: undefined as 'reel' | 'post' | 'carousel' | 'story' | undefined,
    sort: 'sent_at_desc' as 'sent_at_desc' | 'sent_at_asc',
  });

  const { data: queue, isLoading, error, refetch } = useQueue(threadId, filters);
  const { mutate: startScan } = useStartScan();
  const { data: threads } = useThreads();

  const thread = threads?.find(t => t.id === threadId);

  const handleScanNowInternal = () => {
    if (!thread) return;

    startScan(
      { thread_url: thread.thread_url, max_messages: 200 },
      {
        onSuccess: () => {
          refetch();
        },
        onError: (error) => {
          if (error.message.includes('Scan already in progress')) {
            // Toast already shown by mutation error handling
          }
        },
      }
    );
  };

  const handleLoadMore = () => {
    refetch();
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <ItemCardSkeleton count={8} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-semibold text-ig-text">Failed to load items</div>
          <div className="mt-2 text-ig-muted">Please try again later</div>
        </div>
      </div>
    );
  }

  if (!queue || queue.items.length === 0) {
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
            @{thread?.participant_handle} • {queue.total} items • {thread?.unwatched_count} unwatched
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Sort toggle */}
          <Select
            value={filters.sort}
            onChange={(e) => setFilters({ ...filters, sort: e.target.value as 'sent_at_desc' | 'sent_at_asc' })}
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
        {queue.items.map((item) => (
          <ItemCard key={item.id} item={item} />
        ))}
      </div>

      {/* Load more */}
      {queue.items.length < queue.total && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={handleLoadMore}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}
