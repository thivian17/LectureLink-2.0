import { test as setup, expect } from '@playwright/test';
import path from 'path';

export const AUTH_STATE_PATH = path.join(__dirname, '../.auth/user.json');

setup('authenticate', async ({ page }) => {
  await page.goto('/login');

  const email = process.env.E2E_TEST_EMAIL!;
  const password = process.env.E2E_TEST_PASSWORD!;

  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in|log in/i }).click();

  await page.waitForURL('/dashboard', { timeout: 10_000 });
  await expect(page).toHaveURL('/dashboard');

  await page.context().storageState({ path: AUTH_STATE_PATH });
});
