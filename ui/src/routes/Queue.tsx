import { useParams } from 'react-router-dom';
import { QueueGrid } from '../components/queue/QueueGrid';
import { AddThreadModal } from '../components/modals/AddThreadModal';
import { useState } from 'react';
import { Button } from '../components/ui/button';

export function Queue() {
  const { threadId } = useParams<{ threadId: string }>();
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ig-text">Queue</h1>
        <Button onClick={() => setIsAddModalOpen(true)}>
          Add thread
        </Button>
      </div>

      {threadId && (
        <QueueGrid
          threadId={parseInt(threadId, 10)}
        />
      )}

      <AddThreadModal
        open={isAddModalOpen}
        onOpenChange={setIsAddModalOpen}
      />
    </div>
  );
}
