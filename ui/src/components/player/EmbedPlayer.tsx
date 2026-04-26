import { Item } from '../../types/api';

interface EmbedPlayerProps {
  item: Item;
}

export function EmbedPlayer({ item }: EmbedPlayerProps) {
  if (item.item_type === 'story') {
    return (
      <div className="flex max-w-[540px] flex-col items-center justify-center space-y-4 rounded-xl bg-ig-surface p-8 text-center">
        <div className="text-lg font-semibold text-ig-text">Story Expired</div>
        <div className="text-ig-muted">
          Story content has expired and cannot be played. Stories are only available for 24 hours.
        </div>
        <div className="space-y-2 text-sm text-ig-muted">
          <div>
            <span className="font-medium">From:</span> @{item.poster_handle}
          </div>
          {item.sent_at && (
            <div>
              <span className="font-medium">Sent:</span> {new Date(item.sent_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>
    );
  }

  let embedUrl = '';
  if (item.item_type === 'reel') {
    embedUrl = `https://www.instagram.com/reel/${item.media_shortcode}/embed/captioned/`;
  } else if (item.item_type === 'post' || item.item_type === 'carousel') {
    embedUrl = `https://www.instagram.com/p/${item.media_shortcode}/embed/captioned/`;
  }

  return (
    <div className="flex max-w-[540px] flex-col items-center">
      <div className="w-full rounded-xl bg-ig-surface">
        <iframe
          src={embedUrl}
          width="540"
          height="720"
          frameBorder="0"
          scrolling="no"
          allowTransparency={true}
          allow="encrypted-media"
          className="w-full"
          title={`Instagram ${item.item_type} from @${item.poster_handle}`}
        />
      </div>
    </div>
  );
}
