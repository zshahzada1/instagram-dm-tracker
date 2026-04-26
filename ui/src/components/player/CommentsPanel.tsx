import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, MessageCircle, X, CheckCircle } from 'lucide-react';
import { Button } from '../ui/button';

interface CommentUser {
  id: string;
  username: string;
  profile_pic_url: string;
  is_verified: boolean;
}

interface Comment {
  pk: string;
  text: string;
  created_at: number;
  comment_like_count: number;
  child_comment_count: number;
  has_liked_comment: boolean;
  is_edited: boolean;
  has_gif: boolean;
  user: CommentUser;
}

interface CommentsResponse {
  item_id: number;
  media_id: string;
  comments: Comment[];
  has_next_page: boolean;
  end_cursor: string | null;
  total_fetched: number;
}

interface CommentsPanelProps {
  itemId: number;
  visible: boolean;
  onClose: () => void;
}

export function CommentsPanel({ itemId, visible, onClose }: CommentsPanelProps) {
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasFetched, setHasFetched] = useState(false);

  const fetchComments = async () => {
    if (!visible || loading) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8000/comments/${itemId}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch comments');
      }
      const data: CommentsResponse = await response.json();
      setComments(data.comments);
      setHasFetched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible && !hasFetched) {
      fetchComments();
    }
  }, [visible, hasFetched]);

  const formatTimestamp = (timestamp: number): string => {
    const now = Math.floor(Date.now() / 1000);
    const diff = now - timestamp;

    const minutes = Math.floor(diff / 60);
    const hours = Math.floor(diff / 3600);
    const days = Math.floor(diff / 86400);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return new Date(timestamp * 1000).toLocaleDateString();
  };

  if (!visible) {
    return null;
  }

  return (
    <div className="rounded-lg border border-ig-border bg-ig-surface p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-ig-text">
          <MessageCircle className="h-5 w-5" />
          Comments
        </h2>
        <Button variant="ghost" size="sm" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {!hasFetched && !loading && (
        <div className="text-center">
          <Button onClick={fetchComments} size="lg">
            <MessageCircle className="mr-2 h-4 w-4" />
            Load comments
          </Button>
          <p className="mt-2 text-sm text-ig-muted">
            Opens a browser to fetch comments (~15-25 seconds)
          </p>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2 className="mb-4 h-8 w-8 animate-spin text-ig-accent" />
          <p className="text-ig-text">Loading comments…</p>
          <p className="mt-1 text-sm text-ig-muted">This takes 15-25 seconds</p>
        </div>
      )}

      {error && (
        <div className="text-center py-8">
          <p className="mb-4 text-ig-text">{error}</p>
          <Button onClick={fetchComments} variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </div>
      )}

      {comments !== null && !loading && !error && (
        <div className="space-y-4">
          {comments.length === 0 ? (
            <p className="py-8 text-center text-ig-muted">No comments found</p>
          ) : (
            comments.map((comment) => (
              <div key={comment.pk} className="flex gap-3 rounded-lg p-3 hover:bg-ig-muted/20">
                <img
                  src={comment.user.profile_pic_url}
                  alt={comment.user.username}
                  className="h-10 w-10 rounded-full object-cover"
                  onError={(e) => {
                    e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="40" height="40"%3E%3Crect width="40" height="40" fill="%23e0e0e0"/%3E%3C/svg%3E';
                  }}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-ig-text">
                      @{comment.user.username}
                    </span>
                    {comment.user.is_verified && (
                      <CheckCircle className="h-4 w-4 fill-ig-accent text-ig-accent" />
                    )}
                    <span className="text-xs text-ig-muted">
                      {formatTimestamp(comment.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 text-ig-text">{comment.text}</p>
                  <div className="mt-2 flex items-center gap-4 text-sm text-ig-muted">
                    {comment.comment_like_count > 0 && (
                      <span>❤ {comment.comment_like_count}</span>
                    )}
                    {comment.child_comment_count > 0 && (
                      <span>💬 {comment.child_comment_count} replies</span>
                    )}
                    {comment.is_edited && (
                      <span className="italic">(edited)</span>
                    )}
                    {comment.has_gif && (
                      <span className="rounded bg-ig-accent px-2 py-0.5 text-xs font-medium text-white">
                        GIF
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
