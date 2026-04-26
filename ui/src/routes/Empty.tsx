import { useState } from 'react';
import { AddThreadModal } from '../components/modals/AddThreadModal';
import { Button } from '../components/ui/button';

export function Empty() {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <div className="flex h-screen items-center justify-center bg-ig-background text-ig-text">
      <div className="max-w-md space-y-6 text-center">
        <h1 className="text-3xl font-semibold">No threads yet</h1>
        <p className="text-lg text-ig-muted">
          Click the button below to scan your first DM thread.
        </p>
        <Button
          size="lg"
          onClick={() => setIsModalOpen(true)}
        >
          Add your first thread
        </Button>
        <AddThreadModal
          open={isModalOpen}
          onOpenChange={setIsModalOpen}
        />
      </div>
    </div>
  );
}
