import { Dialog, DialogHeader, DialogTitle, DialogContent } from '../ui/dialog';

interface ScanModalProps {
  open: boolean;
}

export function ScanModal({ open }: ScanModalProps) {
  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogHeader>
        <DialogTitle>Scanning Thread…</DialogTitle>
      </DialogHeader>

      <DialogContent>
        <div className="flex flex-col items-center space-y-4 py-8">
          {/* Spinner */}
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-ig-border border-t-ig-accent" />

          {/* Message */}
          <div className="text-center">
            <div className="text-lg font-semibold text-ig-text">Scanning thread…</div>
            <div className="mt-2 text-ig-muted">
              This can take up to a minute. A Camoufox browser window will open on your machine during the scan — that's normal, leave it alone.
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
