import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    // Always test against the built production bundle served by the backend.
    // This is the same URL used in production, not the Vite dev server.
    baseURL: 'http://127.0.0.1:9099',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // Only one server: the FastAPI backend serving the built static files.
  // Run `bash dev.sh` (or `bash smoke.sh`) to ensure the bundle is built first.
  webServer: {
    command: 'uv run uvicorn agent_publisher.main:app --host 127.0.0.1 --port 9099',
    cwd: '..',
    url: 'http://127.0.0.1:9099/api/version',
    reuseExistingServer: true,  // reuse if already running (e.g. from dev.sh)
    timeout: 30_000,
  },
});
