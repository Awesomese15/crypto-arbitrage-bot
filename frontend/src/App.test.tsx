// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const routeA = 'Route A: USDT -> BTC -> ETH -> USDT'
const routeB = 'Route B: USDT -> ETH -> BTC -> USDT'
const config = {
  starting_amount: '125', fee_rate: '0.002', safety_threshold_pct: '0.15',
  poll_interval_seconds: 7, receive_skew_threshold_seconds: 2,
}
const status = { running: false, config, latest_scan: null, last_error: null }
const history = { observations: [] }

function response(body: unknown, ok = true) {
  return { ok, json: async () => body }
}

function mockApi() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.endsWith('/status')) return Promise.resolve(response(status))
    if (url.includes('/observations')) return Promise.resolve(response(history))
    throw new Error(`Unexpected GET ${url}`)
  })
}

async function flushRequests() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('dashboard configuration lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', mockApi())
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('uses exact ASCII route values while displaying Unicode arrows', () => {
    render(<App />)
    expect(screen.getByRole('option', { name: 'Route A: USDT → BTC → ETH → USDT' })).toHaveValue(routeA)
    expect(screen.getByRole('option', { name: 'Route B: USDT → ETH → BTC → USDT' })).toHaveValue(routeB)
  })

  it('loads configuration after the first successful status response', async () => {
    render(<App />)
    await flushRequests()
    expect(screen.getByLabelText('Amount (USDT)')).toHaveValue(125)
    expect(screen.getByLabelText('Fee / leg')).toHaveValue(0.002)
    expect(screen.getByLabelText('Threshold (%)')).toHaveValue(0.15)
    expect(screen.getByLabelText('Polling (seconds)')).toHaveValue(7)
  })

  it('preserves unsaved edits during periodic refresh', async () => {
    render(<App />)
    await flushRequests()
    fireEvent.change(screen.getByLabelText('Amount (USDT)'), { target: { value: '333' } })

    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    await flushRequests()

    expect(screen.getByLabelText('Amount (USDT)')).toHaveValue(333)
  })

  it('saves configuration and adopts the backend response', async () => {
    const fetchMock = mockApi()
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/config') && init?.method === 'POST') {
        return Promise.resolve(response({ ...config, starting_amount: '333' }))
      }
      if (url.endsWith('/status')) return Promise.resolve(response(status))
      if (url.includes('/observations')) return Promise.resolve(response(history))
      throw new Error(`Unexpected request ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await flushRequests()
    fireEvent.change(screen.getByLabelText('Amount (USDT)'), { target: { value: '333' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save config' }))

    await flushRequests()
    expect(screen.getByLabelText('Amount (USDT)')).toHaveValue(333)
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/config', expect.objectContaining({ method: 'POST' }))
  })
})
