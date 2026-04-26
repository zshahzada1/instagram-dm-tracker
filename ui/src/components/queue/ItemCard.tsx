import { Link } from 'react-router-dom';
import { Item } from '../../types/api';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { getItemThumbnailUrl } from '../../api/items';

interface ItemCardProps {
  item: Item;
}

export function ItemCard({ item }: ItemCardProps) {
  return (
    <Link
      to={`/threads/${item.thread_id}/items/${item.id}`}
      className="group relative overflow-hidden rounded-xl border border-ig-border bg-ig-surface transition-all hover:border-ig-accent hover:shadow-lg"
    >
      {/* Thumbnail */}
      <div className="relative aspect-square bg-ig-background">
        <img
          src={getItemThumbnailUrl(item.id)}
          alt={item.caption || `Media from @${item.poster_handle}`}
          className="h-full w-full object-cover"
          onError={(e) => {
            e.currentTarget.style.display = 'none';
            e.currentTarget.nextElementSibling?.classList.remove('hidden');
          }}
        />
        <div className="hidden absolute inset-0 flex items-center justify-center bg-ig-border text-ig-muted">
          No preview
        </div>

        {/* Type badge */}
        <div className="absolute right-2 top-2">
          <Badge
            variant={item.watched ? 'secondary' : 'default'}
            className="text-xs"
          >
            {item.item_type.toUpperCase()}
          </Badge>
        </div>

        {/* Watched indicator */}
        {item.watched && (
          <div className="absolute bottom-2 right-2 h-3 w-3 rounded-full bg-green-500" />
        )}

        {/* Expired overlay for stories */}
        {item.item_type === 'story' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-white text-sm font-semibold">
            EXPIRED
          </div>
        )}

        {/* Reaction indicator */}
        {item.my_existing_reaction && (
          <div className="absolute bottom-2 left-2 text-lg">
            {item.my_existing_reaction}
          </div>
        )}
      </div>

      {/* Metadata */}
      <div className="p-3">
        <div className="text-sm font-medium text-ig-text">
          @{item.poster_handle}
        </div>
        {item.caption && (
          <div className="mt-1 text-xs text-ig-muted line-clamp-2">
            {item.caption}
          </div>
        )}
        <div className="mt-2 text-xs text-ig-muted">
          {formatRelativeTime(item.sent_at)}
        </div>
      </div>
    </Link>
  );
}

interface ItemCardSkeletonProps {
  count?: number;
}

export function ItemCardSkeleton({ count = 1 }: ItemCardSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="overflow-hidden rounded-xl border border-ig-border bg-ig-surface"
        >
          <Skeleton className="aspect-square" />
          <div className="p-3 space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        </div>
      ))}
    </>
  );
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  const minutes = Math.floor(diff / (1000 * 60));
  if (minutes > 0) return `${minutes}m ago`;
  return 'Just now';
}
