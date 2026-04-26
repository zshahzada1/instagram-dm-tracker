import { useSettings } from '../hooks/queries/useSettings';
import { useUpdateSettings } from '../hooks/mutations/useUpdateSettings';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Select } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';

export function Settings() {
  const { data: settings, isLoading } = useSettings();
  const { mutate: updateSetting } = useUpdateSettings();

  const handleUpdateSetting = (key: string, value: string) => {
    updateSetting(
      { key, value },
      {
        onSuccess: () => {
          toast.success('Setting updated');
        },
        onError: (error) => {
          toast.error(`Failed to update setting: ${error.message}`);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-ig-background text-ig-text">
        <div>Loading settings...</div>
      </div>
    );
  }

  const sortOrder = settings?.find(s => s.key === 'sort_order')?.value;
  const autoNextEnabled = settings?.find(s => s.key === 'auto_next_enabled')?.value === '1';
  const defaultReactionEmoji = settings?.find(s => s.key === 'default_reaction_emoji')?.value;
  const autoReactEnabled = settings?.find(s => s.key === 'auto_react_enabled')?.value === '1';
  const autoRefreshMinutes = settings?.find(s => s.key === 'auto_refresh_minutes')?.value;

  return (
    <div className="max-w-2xl p-6">
      <h1 className="mb-6 text-3xl font-semibold text-ig-text">Settings</h1>

      <div className="space-y-4">
        {/* Sort Order */}
        <Card>
          <CardHeader>
            <CardTitle>Sort Order</CardTitle>
          </CardHeader>
          <CardContent>
            <Select
              value={sortOrder || 'sent_at_desc'}
              onChange={(e) => handleUpdateSetting('sort_order', e.target.value)}
            >
              <option value="sent_at_desc">Newest first</option>
              <option value="sent_at_asc">Oldest first</option>
              <option value="first_seen_desc">First seen first</option>
            </Select>
            <p className="mt-2 text-sm text-ig-muted">
              Default sort order for the queue view.
            </p>
          </CardContent>
        </Card>

        {/* Auto Next */}
        <Card>
          <CardHeader>
            <CardTitle>Auto-advance</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div>
              <div className="font-medium text-ig-text">Auto-advance to next item</div>
              <p className="mt-1 text-sm text-ig-muted">
                When enabled, automatically navigate to the next unwatched item after marking one as watched.
              </p>
            </div>
            <Switch
              checked={autoNextEnabled}
              onCheckedChange={(checked) => handleUpdateSetting('auto_next_enabled', checked ? '1' : '0')}
            />
          </CardContent>
        </Card>

        {/* Default Reaction Emoji (P6 - disabled) */}
        <Card>
          <CardHeader>
            <CardTitle>Default Reaction Emoji</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded bg-ig-background px-4 py-2 text-center text-2xl">
              {defaultReactionEmoji || '❤'}
            </div>
            <p className="mt-2 text-sm text-ig-muted">
              Coming in Phase 6
            </p>
          </CardContent>
        </Card>

        {/* Auto React (P6 - disabled) */}
        <Card>
          <CardHeader>
            <CardTitle>Auto-react</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div>
              <div className="font-medium text-ig-text">Automatically react to new items</div>
              <p className="mt-1 text-sm text-ig-muted">
                When enabled, automatically send the default reaction emoji to new items as they're scanned.
              </p>
            </div>
            <Switch
              checked={autoReactEnabled}
              onCheckedChange={() => {}}
              disabled
            />
          </CardContent>
          <CardContent className="text-sm text-ig-muted">
            Coming in Phase 6
          </CardContent>
        </Card>

        {/* Auto Refresh (P7 - disabled) */}
        <Card>
          <CardHeader>
            <CardTitle>Auto-refresh</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <label className="mb-2 block text-sm font-medium text-ig-text">
                  Refresh interval (minutes)
                </label>
                <div className="rounded bg-ig-background px-4 py-2 text-center">
                  {autoRefreshMinutes || '5'}
                </div>
              </div>
            </div>
            <p className="mt-2 text-sm text-ig-muted">
              Coming in Phase 7
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
