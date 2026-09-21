import { expect, test } from '@playwright/test'

test('dashboard renders metrics computed from connector data', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Ask your workspace' })).toBeVisible()

  // Metric values come from the API, so wait for a non-zero count to appear.
  // Match on the label element exactly: several metrics mention "open work" in prose.
  const metricValue = (label: string) =>
    page.locator('.metric-copy').filter({ has: page.getByText(label, { exact: true }) }).locator('strong')

  const issuesInScope = metricValue('Issues in scope')
  await expect(issuesInScope).not.toHaveText('0', { timeout: 15_000 })

  const total = Number(await issuesInScope.textContent())
  const open = Number(await metricValue('Open work').textContent())
  expect(total).toBeGreaterThan(0)
  expect(open).toBeLessThanOrEqual(total)

  // The connector must report itself connected, not a hardcoded status.
  await expect(page.locator('.source-row')).toContainText('records')

  // The chart is drawn from real series data.
  await expect(page.locator('svg .teal-line')).toHaveAttribute('d', /^M[\d.]/)

  expect(errors).toEqual([])
})

test('asking a question renders backend-computed cards', async ({ page }) => {
  await page.goto('/')
  await page.getByPlaceholder('Ask anything, or ask for a chart').fill('what is overdue?')
  await page.keyboard.press('Enter')

  await expect(page.locator('.turn-assistant p').first()).toBeVisible({ timeout: 20_000 })
  await expect(page.locator('.card-grid .card').first()).toBeVisible()

  // A metric card's value is computed server-side from records.
  const metricCard = page.locator('.card-metric').first()
  await expect(metricCard.locator('.card-value')).toHaveText(/^\d+$/)

  // A table card renders the columns the spec asked for.
  await expect(page.locator('.card-table th').first()).toBeVisible()
})
