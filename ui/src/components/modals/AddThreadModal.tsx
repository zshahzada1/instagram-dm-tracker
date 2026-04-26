import { useState } from 'react';
import { Dialog, DialogHeader, DialogTitle, DialogContent, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useStartScan } from '../../hooks/mutations/useStartScan';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

interface AddThreadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddThreadModal({ open, onOpenChange }: AddThreadModalProps) {
  const [url, setUrl] = useState('');
  const [maxMessages, setMaxMessages] = useState(200);
  const { mutate: startScan, isPending: isScanning } = useStartScan();
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validate URL format
    if (!url.includes('instagram.com/direct/t/')) {
      toast.error('Invalid URL. Please enter a valid Instagram DM thread URL.');
      return;
    }

    startScan(
      { thread_url: url, max_messages: maxMessages },
      {
        onSuccess: (response) => {
          if (response.success && response.thread_id) {
            toast.success(
              `Found ${response.items_inserted} new items, ${response.items_ignored} already tracked`
            );
            onOpenChange(false);
            setUrl('');
            navigate(`/threads/${response.thread_id}`);
          } else if (response.error) {
            toast.error(`Scan failed: ${response.error}`);
          }
        },
        onError: (error) => {
          if (error.message.includes('Scan already in progress')) {
            toast.error('A scan is already running.');
          } else {
            toast.error(`Failed to start scan: ${error.message}`);
          }
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <DialogTitle>Add Thread</DialogTitle>
      </DialogHeader>

      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-ig-text">
              Instagram DM thread URL
            </label>
            <Input
              type="url"
              placeholder="https://www.instagram.com/direct/t/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isScanning}
            />
            <p className="mt-2 text-xs text-ig-muted">
              Each thread is tracked separately. Adding bel's DMs and someone else's keeps them isolated — they don't mix.
            </p>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-ig-text">
              Max messages
            </label>
            <Input
              type="number"
              min="50"
              max="2000"
              value={maxMessages}
              onChange={(e) => setMaxMessages(parseInt(e.target.value) || 200)}
              disabled={isScanning}
            />
            <p className="mt-2 text-xs text-ig-muted">
              Range: 50-2000 messages. Default: 200.
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isScanning}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isScanning || !url}>
              {isScanning ? 'Starting scan...' : 'Start scan'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
