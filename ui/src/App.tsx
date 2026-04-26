import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { Root } from './routes/Root';
import { Queue } from './routes/Queue';
import { Player } from './routes/Player';
import { Settings } from './routes/Settings';
import { Empty } from './routes/Empty';
import { Toaster } from 'sonner';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Root />} />
            <Route path="empty" element={<Empty />} />
            <Route path="threads/:threadId" element={<Queue />} />
            <Route path="threads/:threadId/items/:itemId" element={<Player />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
