import { test, expect } from '@playwright/test'
const api = 'http://localhost:8015'

test('connect, generate, edit, publish, verify, refresh and recover a bulk run', async ({ page, request }) => {
  const email = `journey-${Date.now()}@example.com`
  const password = 'JourneyPass123!'
  const signup = await request.post(`${api}/api/v1/auth/signup`, { data: { email, password } })
  expect(signup.status()).toBe(201)
  const login = await request.post(`${api}/api/v1/auth/login`, { form: { username: email, password } })
  const { access_token } = await login.json()
  const headers = { Authorization: `Bearer ${access_token}` }
  const domainResponse = await request.post(`${api}/api/v1/domains`, { headers, data: { name: 'journey.test', environment: 'production' } })
  expect(domainResponse.status()).toBe(201)
  const domain = await domainResponse.json()
  await request.post(`${api}/__fixture/verify/${domain.id}`)
  await page.addInitScript(token => localStorage.setItem('access_token', token), access_token)
  await page.goto('/app/previews')
  await page.getByRole('button', { name: 'Create Preview', exact: true }).click()
  await page.getByPlaceholder('https://example.com/page').fill('https://journey.test/')
  await page.getByRole('button', { name: 'Generate with AI', exact: true }).click()
  await expect(page.getByText('A useful page', { exact: true }).first()).toBeVisible()
  const previews = await (await request.get(`${api}/api/v1/previews`, { headers })).json()
  const preview = previews.find((p: { url: string }) => p.url === 'https://journey.test/')
  expect(preview).toBeTruthy()
  await page.getByTitle('See how it looks on each platform').first().click()
  await page.getByRole('tab', { name: 'Edit card' }).click()
  await page.getByLabel('Headline', { exact: true }).fill('Approved headline')
  await page.getByLabel('Lock title', { exact: true }).check()
  await page.getByRole('button', { name: 'Save draft', exact: true }).click()
  await expect(page.getByText('Draft saved. Review all formats, then publish when ready.')).toBeVisible()
  const served = () => request.get(`${api}/api/v1/public/preview?full_url=${encodeURIComponent('https://journey.test/')}`, { headers: { 'User-Agent': 'Twitterbot/1.0' } }).then(r => r.json())
  expect((await served()).title).toBe('A useful page')
  await page.getByRole('button', { name: 'Publish saved draft', exact: true }).click()
  await expect.poll(async () => (await served()).title).toBe('Approved headline')
  const delivery = await request.post(`${api}/api/v1/install/share-check`, { headers, data: { domain_id: domain.id } })
  expect((await delivery.json()).ready).toBe(true)
  for (const alt of ['Currently published card', 'wide card', 'square card', 'portrait card']) {
    await expect.poll(async () => page.getByAltText(alt, { exact: true }).evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  }
  await page.getByAltText('Currently published card', { exact: true }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: 'work/journey-editor.png', fullPage: true })
  // A changed source refreshes the draft, preserving the locked title and live card.
  await request.post(`${api}/__fixture/source`, { data: { title: 'Changed source title', description: 'Updated source copy.' } })
  await request.put(`${api}/api/v1/coverage/${domain.id}`, { headers, data: { enabled: true, interval_hours: 24 } })
  await request.post(`${api}/api/v1/coverage/${domain.id}/scan`, { headers })
  await expect.poll(async () => {
    const coverage = await (await request.get(`${api}/api/v1/coverage/${domain.id}`, { headers })).json()
    return coverage.pages[0]?.state
  }, { timeout: 90000 }).toBe('ready')
  const studio = await (await request.get(`${api}/api/v1/previews/${preview.id}/studio`, { headers })).json()
  expect(studio.title).toBe('Approved headline')
  expect(studio.description).toBe('Updated source copy.')
  expect(studio.has_draft).toBe(true)
  expect((await served()).description).toBe('A clear description from the source page.')
  expect((await served()).title).toBe('Approved headline')
  const bulk = await (await request.post(`${api}/api/v1/jobs/preview/bulk`, { headers, data: { domain: 'journey.test', urls: ['https://journey.test/ok', 'https://journey.test/fails'] } })).json()
  const status = () => request.get(`${api}/api/v1/jobs/bulk/${bulk.batch_id}/status`, { headers }).then(r => r.json())
  await expect.poll(async () => (await status()).status, { timeout: 90000 }).toBe('partial')
  const successfulId = (await status()).results.find((r: { status: string }) => r.status === 'finished').preview_id
  await request.post(`${api}/api/v1/jobs/bulk/${bulk.batch_id}/control`, { headers, data: { action: 'retry_failed' } })
  await expect.poll(async () => (await status()).status, { timeout: 90000 }).toBe('completed')
  expect((await status()).results.find((r: { url: string }) => r.url.endsWith('/ok')).preview_id).toBe(successfulId)
  await page.goto('/app/coverage')
  await expect(page.getByRole('heading', { name: 'Site coverage' })).toBeVisible()
  await expect(page.getByText('ready: 1')).toBeVisible()
})
