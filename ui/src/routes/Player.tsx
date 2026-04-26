import { useParams } from 'react-router-dom';
import { PlayerView } from '../components/player/PlayerView';

export function Player() {
  const { threadId, itemId } = useParams<{ threadId: string; itemId: string }>();

  if (!threadId || !itemId) {
    return (
      <div className="flex h-screen items-center justify-center bg-ig-background text-ig-text">
        <div>Invalid URL</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <PlayerView
        threadId={parseInt(threadId, 10)}
        itemId={parseInt(itemId, 10)}
      />
    </div>
  );
}
