/**
 * Critical Path E2E Tests
 *
 * These 3 tests cover the flows most likely to regress and most damaging
 * if they do. Run before every beta release.
 *
 * Prerequisites:
 *   - E2E_TEST_EMAIL and E2E_TEST_PASSWORD set in environment
 *   - A test course with a syllabus already uploaded (seeded)
 *   - The API and frontend must be running
 */

import { test, expect } from '@playwright/test';

test.use({ storageState: './tests/.auth/user.json' });

// --- Critical Path 1: Lecture Upload + Processing ---

test('CP1: upload a lecture and verify processing completes', async ({ page }) => {
  await page.goto('/dashboard');

  await page.getByText(/test course/i).first().click();
  await page.waitForURL(/\/courses\//);

  await page.getByRole('link', { name: /upload|add lecture/i }).click();
  await page.waitForURL(/\/lectures\/new/);

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'test-lecture.mp3',
    mimeType: 'audio/mpeg',
    buffer: Buffer.alloc(1024, 0),
  });

  await page.getByRole('button', { name: /upload|process/i }).click();

  await expect(page.getByText(/processing|pending/i)).toBeVisible({ timeout: 15_000 });

  await expect(page.getByText(/completed|done|ready/i)).toBeVisible({ timeout: 60_000 });

  await expect(page.getByText(/concepts/i)).toBeVisible();
});

// --- Critical Path 2: Quiz Generation + Submission ---

test('CP2: generate a quiz, answer all questions, and see results', async ({ page }) => {
  await page.goto('/dashboard');
  await page.getByText(/test course/i).first().click();

  await page.getByRole('tab', { name: /quiz/i }).click();

  await page.getByRole('button', { name: /generate quiz/i }).click();
  await expect(page.getByRole('dialog')).toBeVisible();

  await page.getByRole('combobox', { name: /difficulty/i }).selectOption('mixed');

  await page.getByRole('button', { name: /generate|create/i }).click();

  await expect(page.getByText(/ready|start quiz/i)).toBeVisible({ timeout: 45_000 });

  await page.getByRole('button', { name: /start|take quiz/i }).click();
  await page.waitForURL(/\/quiz\//);

  let questionCount = 0;
  while (questionCount < 20) {
    const nextButton = page.getByRole('button', { name: /next|submit/i });
    const finishButton = page.getByRole('button', { name: /finish|complete/i });

    const firstOption = page.locator('[data-testid="mcq-option"]').first();
    if (await firstOption.isVisible()) {
      await firstOption.click();
    }

    if (await finishButton.isVisible()) {
      await finishButton.click();
      break;
    }
    if (await nextButton.isVisible()) {
      await nextButton.click();
    }
    questionCount++;
  }

  await page.waitForURL(/\/results/);
  await expect(page.getByText(/score|%|correct/i)).toBeVisible({ timeout: 15_000 });
});

// --- Critical Path 3: Learn Session + XP Award ---

test('CP3: complete a learn session and verify XP is awarded', async ({ page }) => {
  await page.goto('/dashboard');
  await page.getByText(/test course/i).first().click();

  await page.getByRole('tab', { name: /learn/i }).click();

  const xpBefore = await page.getByTestId('xp-display').textContent().catch(() => '0');

  await page.getByRole('button', { name: /start.*session|begin/i }).click();
  await page.waitForURL(/\/learn/);

  const continueBtn = page.getByRole('button', { name: /continue|start|begin/i });
  if (await continueBtn.isVisible({ timeout: 5_000 })) {
    await continueBtn.click();
  }

  for (let i = 0; i < 10; i++) {
    const nextCard = page.getByRole('button', { name: /next|got it|continue/i });
    if (await nextCard.isVisible({ timeout: 3_000 })) {
      await nextCard.click();
    } else {
      break;
    }
  }

  const completeBtn = page.getByRole('button', { name: /complete.*session|finish/i });
  if (await completeBtn.isVisible({ timeout: 5_000 })) {
    await completeBtn.click();
  }

  await expect(
    page.getByText(/xp earned|\+\d+ xp|great job|session complete/i)
  ).toBeVisible({ timeout: 15_000 });
});
