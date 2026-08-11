import { test, expect } from '@playwright/test'

/**
 * Public-surface smoke: the pages a visitor can reach without an account
 * render their key content. Backend-independent (all static/public routes).
 */

test('landing page renders hero and pricing', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.locator('#pricing')).toBeVisible()
})

test('demo page renders the URL form', async ({ page }) => {
  await page.goto('/demo')
  await expect(page.locator('#url')).toBeVisible()
})

test('login page renders and links to signup + reset', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /forgot password/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /sign up/i })).toBeVisible()
})

test('legal pages exist', async ({ page }) => {
  await page.goto('/terms')
  await expect(page.getByRole('heading', { name: /terms of service/i })).toBeVisible()
  await page.goto('/privacy')
  await expect(page.getByRole('heading', { name: /privacy policy/i })).toBeVisible()
})

test('unknown routes show the 404 page, not a silent redirect', async ({ page }) => {
  await page.goto('/this-page-does-not-exist')
  await expect(page.getByText(/doesn't exist/i)).toBeVisible()
})
