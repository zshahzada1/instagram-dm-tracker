import { useItem } from '../../hooks/queries/useItems';
import { useUpdateWatched } from '../../hooks/mutations/useUpdateWatched';
import { useReact } from '../../hooks/mutations/useReact';
import { useNextUnwatchedItem } from '../../hooks/business/usePlayerFlow';
import { EmbedPlayer } from './EmbedPlayer';
import { Button } from '../ui/button';
import { Link } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useSettings } from '../../hooks/queries/useSettings';
import { Loader2 } from 'lucide-react';

interface PlayerViewProps {
  threadId: number;
  itemId: number;
}

export function PlayerView({ threadId, itemId }: PlayerViewProps) {
  const navigate = useNavigate();
  const { data: item, isLoading, error } = useItem(itemId);
  const { mutate: updateWatched, isPending: isUpdatingWatched } = useUpdateWatched();
  const { mutate: sendReactionMutate, isPending: isReacting } = useReact();
  const { data: nextItem, isLoading: isLoadingNext } = useNextUnwatchedItem(threadId, itemId);
  const { data: settings } = useSettings();

  const autoNextEnabled = settings?.find(s => s.key === 'auto_next_enabled')?.value === '1';

  const handleMarkWatched = () => {
    if (!item) return;

    const newWatchedState = !item.watched;

    updateWatched(
      { id: item.id, watched: newWatchedState },
      {
        onSuccess: () => {
          if (newWatchedState) {
            toast.success('Marked as watched');

            // Auto-advance to next unwatched item if enabled
            if (autoNextEnabled && nextItem) {
              navigate(`/threads/${threadId}/items/${nextItem.id}`);
            } else if (!nextItem) {
              // No more unwatched items, go back to queue
              navigate(`/threads/${threadId}`);
            }
          } else {
            toast.info('Marked as unwatched');
          }
        },
        onError: (error) => {
          toast.error(`Failed to update watched status: ${error.message}`);
        },
      }
    );
  };

  const handleSendReaction = () => {
    if (!item) return;
    sendReactionMutate(
      { item_id: item.id, emoji: '❤' },
      {
        onSuccess: (data) => {
          if (data.status === 'success') {
            toast.success('Heart reaction sent ✓');
          } else if (data.status === 'already_reacted') {
            toast.info('Already reacted to this one');
          }
        },
        onError: (error) => {
          toast.error(`Reaction failed: ${error.message}`);
        },
      }
    );
  };

  const hasReacted = item?.my_auto_sent_reaction === '❤' || item?.my_existing_reaction === '❤';

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-ig-muted">Loading...</div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-semibold text-ig-text">Failed to load item</div>
          <div className="mt-2 text-ig-muted">{error?.message || 'Item not found'}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top bar with back button and metadata */}
      <div className="flex items-center gap-4">
        <Link
          to={`/threads/${threadId}`}
          className="flex items-center text-ig-muted hover:text-ig-text transition-colors"
        >
          ← Back to queue
        </Link>
        <div className="flex-1">
          <div className="text-lg font-semibold text-ig-text">
            <a
              href={`https://instagram.com/${item.poster_handle}`}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ig-accent transition-colors"
            >
              @{item.poster_handle}
            </a>
          </div>
          <div className="text-sm text-ig-muted">
            {item.sent_at && new Date(item.sent_at).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Caption */}
      {item.caption && (
        <div className="rounded-lg border border-ig-border bg-ig-surface p-4">
          <div className="text-ig-text">{item.caption}</div>
        </div>
      )}

      {/* Player */}
      <EmbedPlayer item={item} />

      {/* Action buttons */}
      <div className="flex items-center justify-center gap-4">
        <Button
          onClick={handleMarkWatched}
          disabled={isUpdatingWatched || isLoadingNext}
          size="lg"
        >
          {item.watched ? 'Mark unwatched' : 'Mark watched'}
        </Button>
        <Button
          variant="outline"
          disabled={hasReacted || isReacting}
          onClick={handleSendReaction}
          size="lg"
        >
          {isReacting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Reacting…
            </>
          ) : hasReacted ? (
            'Heart sent ✓'
          ) : (
            'Send heart ❤'
          )}
        </Button>
      </div>

      {/* Comments placeholder */}
      <div className="rounded-lg border border-ig-border bg-ig-surface p-6">
        <h2 className="mb-4 text-lg font-semibold text-ig-text">Comments</h2>
        <div className="text-ig-muted">
          Comments and comment reactions are coming in Phase 7.
        </div>
      </div>
    </div>
  );
}
