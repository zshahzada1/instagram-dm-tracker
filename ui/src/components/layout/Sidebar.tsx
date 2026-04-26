import { Link } from 'react-router-dom';
import { useThreads } from '../../hooks/queries/useThreads';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useScans } from '../../hooks/queries/useScans';

export function Sidebar() {
  const { data: threads, isLoading, error } = useThreads();
  const { data: scans } = useScans({ limit: 1 });

  // Check if scan is running
  const isScanning = scans?.some(scan => scan.status === 'running');

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-[260px] border-r border-ig-border bg-ig-surface">
      {/* Header */}
      <div className="p-6 border-b border-ig-border">
        <h1 className="text-xl font-semibold text-ig-text">DM Tracker</h1>
      </div>

      {/* Thread List */}
      <nav className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-lg bg-ig-border animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="text-center text-ig-muted">
            Failed to load threads
          </div>
        ) : threads && threads.length > 0 ? (
          <ul className="space-y-1">
            {threads.map((thread) => (
              <li key={thread.id}>
                <Link
                  to={`/threads/${thread.id}`}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium text-ig-text hover:bg-ig-border transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate">{thread.display_name}</span>
                      {thread.unwatched_count > 0 && (
                        <Badge variant="default" className="text-xs">
                          {thread.unwatched_count}
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-ig-muted">
                      @{thread.participant_handle}
                    </div>
                    <div className="text-xs text-ig-muted">
                      {formatRelativeTime(thread.last_item_sent_at)}
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-center text-ig-muted">
            No threads yet
          </div>
        )}
      </nav>

      {/* Footer */}
      <div className="border-t border-ig-border p-4">
        <Button variant="outline" className="w-full justify-start" onClick={() => {/* TODO: Open add thread modal */}}>
          + Add thread
        </Button>
        <Link to="/settings" className="block mt-2 text-sm text-ig-muted hover:text-ig-text transition-colors">
          Settings
        </Link>

        {/* Scan status pill */}
        <div className="mt-4 rounded-md bg-ig-background px-3 py-2 text-xs">
          {isScanning ? (
            <div className="flex items-center gap-2 text-ig-accent">
              <div className="h-2 w-2 animate-ping rounded-full bg-ig-accent" />
              Scanning…
            </div>
          ) : (
            <div className="text-ig-muted">Scanner idle</div>
          )}
        </div>
      </div>
    </aside>
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
