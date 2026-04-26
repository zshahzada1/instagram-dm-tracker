import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useThreads } from '../hooks/queries/useThreads';

export function Root() {
  const navigate = useNavigate();
  const { data: threads, isLoading } = useThreads();

  useEffect(() => {
    if (!isLoading) {
      if (threads && threads.length > 0) {
        // Redirect to most recently scanned thread
        const mostRecent = threads.sort((a, b) =>
          new Date(b.last_scanned_at || 0).getTime() - new Date(a.last_scanned_at || 0).getTime()
        )[0];
        navigate(`/threads/${mostRecent.id}`, { replace: true });
      } else {
        // Show empty state
        navigate('/empty', { replace: true });
      }
    }
  }, [threads, isLoading, navigate]);

  return <div className="flex h-screen items-center justify-center">Loading...</div>;
}
