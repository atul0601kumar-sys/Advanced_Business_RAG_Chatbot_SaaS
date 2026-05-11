# Embeddable Widget

## Embed Snippet

```html
<script
  src="https://yourdomain.com/widget.js"
  data-workspace-id="YOUR_WORKSPACE_ID"
  data-api-base-url="https://api.yourdomain.com"
  data-position="right"
  data-theme="light"
  data-color="#0ea5e9"
  data-welcome-message="Hi there. Ask about pricing, onboarding, or policies."
></script>
```

## Supported Data Attributes

- `data-workspace-id`
- `data-api-base-url`
- `data-position`
- `data-theme`
- `data-color`
- `data-welcome-message`

## Widget Runtime

- Loader entry: `frontend/public/widget.js`
- Shadow DOM modules: `frontend/public/widget/`
- Demo page: `frontend/public/widget-sample.html`

## Public API Flow

1. `GET /api/v1/settings/public`
2. `POST /api/v1/chat/session`
3. `POST /api/v1/chat/message`
4. `GET /api/v1/chat/history/{session_id}`
5. `POST /api/v1/leads/create`
6. `POST /api/v1/feedback`
7. `POST /api/v1/chat/stop`
8. `POST /api/v1/chat/regenerate`
9. `POST /api/v1/widget/event`

## Local Testing

1. Start the backend on `http://localhost:8000`.
2. Start the frontend on `http://localhost:3000`.
3. Open `http://localhost:3000/widget-sample.html`.
4. Replace the placeholder workspace id in the page source with a real workspace id from your local database.
5. Verify launcher, streaming chat, session persistence, and lead submission.
