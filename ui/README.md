# Instagram DM Tracker - UI

React frontend for the Instagram DM Media Tracker.

## Development

### Prerequisites

- Node.js 18+ and npm
- FastAPI backend running on http://localhost:8000

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at http://localhost:5173

### Build

```bash
npm run build
```

### Environment

Copy `.env.example` to `.env` and configure:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Tech Stack

- React 18 + TypeScript
- Vite
- React Router v6
- TanStack Query v5
- Tailwind CSS
- shadcn/ui components
