export interface Thread {
  id: number;
  ig_thread_id: string;
  display_name: string;
  participant_handle: string;
  thread_url: string;
  last_scanned_at: string;
  auto_refresh_enabled: boolean;
  total_items: number;
  unwatched_count: number;
  last_item_sent_at: string;
  created_at: string;
  updated_at: string;
}

export interface Item {
  id: number;
  thread_id: number;
  ig_message_id: string;
  item_type: 'reel' | 'post' | 'carousel' | 'story';
  media_shortcode: string;
  media_url: string;
  poster_handle: string;
  caption: string | null;
  sent_at: string;
  sender: 'me' | 'her';
  watched: boolean;
  my_existing_reaction: string | null;
  my_auto_sent_reaction: string | null;
  first_seen_at: string;
  created_at: string;
  updated_at: string;
  instagram_url: string | null;
}

export interface ItemsListResponse {
  total: number;
  limit: number;
  offset: number;
  items: Item[];
}

export interface ItemsParams {
  thread_id?: number;
  watched?: boolean;
  item_type?: 'reel' | 'post' | 'carousel' | 'story';
  sender?: 'me' | 'her' | 'all';
  sort?: 'sent_at_desc' | 'sent_at_asc' | 'first_seen_desc';
  limit?: number;
  offset?: number;
}

export interface ItemWatchedUpdate {
  watched: boolean;
}

export interface ScanStartRequest {
  thread_url: string;
  max_messages?: number;
}

export interface ScanResponse {
  success: boolean;
  scan_run_id: number;
  thread_id?: number;
  display_name?: string;
  messages_parsed?: number;
  items_inserted?: number;
  items_ignored?: number;
  item_type_inserted_counts?: {
    reel: number;
    post: number;
    carousel: number;
    story: number;
  };
  pagination?: {
    success: boolean;
    messages_found: number;
    attempts: number;
  };
  error?: string;
}

export interface ScanRun {
  id: number;
  thread_id: number;
  started_at: string;
  completed_at: string | null;
  new_items_found: number;
  status: 'running' | 'completed' | 'failed';
  error_message: string | null;
}

export interface Setting {
  key: string;
  value: string;
  description: string;
  updated_at: string;
}

export interface SettingUpdate {
  value: string;
}
