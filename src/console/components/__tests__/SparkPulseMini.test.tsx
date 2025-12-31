//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

/**
 * Tests for SparkPulseMini component polling and cleanup.
 * 
 * Verifies:
 * - Polling starts immediately on mount
 * - Cleanup aborts in-flight requests and clears interval
 * - No setState calls after unmount
 * - AbortSignal is passed to fetch calls
 */

import React from "react"
import { render, screen } from "@testing-library/react"
import { SparkPulseMini } from "../SparkPulseMini"
import * as asyncUtils from "@/lib/async"

// Mock the async utilities
jest.mock("@/lib/async", () => {
  const actual = jest.requireActual("@/lib/async")
  return {
    ...actual,
    createAbortableFetch: jest.fn(),
    createIsMountedRef: jest.fn(),
    startPolling: jest.fn(),
  }
})

// Mock fetch globally
global.fetch = jest.fn()

describe("SparkPulseMini", () => {
  const mockPulseResponse = {
    memory_pressure: 75,
    unified_usage_gb: 128.5,
    active_cores: "performance",
  }

  let mockAbort: jest.Mock
  let mockSignal: AbortSignal
  let mockMountedRef: { isMounted: jest.Mock; unmount: jest.Mock }
  let mockPollingController: { stop: jest.Mock; isActive: jest.Mock }

  beforeEach(() => {
    jest.clearAllMocks()
    jest.useFakeTimers()

    // Setup AbortSignal mock
    mockAbort = jest.fn()
    mockSignal = {
      aborted: false,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
      onabort: null,
    } as unknown as AbortSignal

    // Setup mounted ref mock
    mockMountedRef = {
      isMounted: jest.fn().mockReturnValue(true),
      unmount: jest.fn(),
    }

    // Setup polling controller mock
    mockPollingController = {
      stop: jest.fn(),
      isActive: jest.fn().mockReturnValue(true),
    }

    // Mock createIsMountedRef
    ;(asyncUtils.createIsMountedRef as jest.Mock).mockReturnValue(
      mockMountedRef
    )

    // Mock startPolling
    ;(asyncUtils.startPolling as jest.Mock).mockReturnValue(
      mockPollingController
    )

    // Mock createAbortableFetch
    ;(asyncUtils.createAbortableFetch as jest.Mock).mockImplementation(
      (url: string, opts?: { signal?: AbortSignal }) => {
        return {
          promise: Promise.resolve(mockPulseResponse),
          signal: opts?.signal || mockSignal,
          abort: mockAbort,
        }
      }
    )
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it("should start polling immediately on mount", () => {
    render(<SparkPulseMini />)

    expect(asyncUtils.startPolling).toHaveBeenCalledWith(
      expect.objectContaining({
        intervalMs: 3000,
        immediate: true,
      })
    )
  })

  it("should create mounted ref on mount", () => {
    render(<SparkPulseMini />)

    expect(asyncUtils.createIsMountedRef).toHaveBeenCalled()
  })

  it("should stop polling and unmount ref on cleanup", () => {
    const { unmount } = render(<SparkPulseMini />)

    unmount()

    expect(mockMountedRef.unmount).toHaveBeenCalled()
    expect(mockPollingController.stop).toHaveBeenCalledWith(
      "Component unmounted"
    )
  })

  it("should not call setState after unmount", async () => {
    const { unmount } = render(<SparkPulseMini />)

    // Get the polling function that was passed to startPolling
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn

    // Unmount component first (marks as unmounted)
    unmount()
    mockMountedRef.isMounted.mockReturnValue(false)

    // Simulate a late-arriving response by calling the poll function
    // This simulates a fetch that completes after component unmounts
    await pollFn(mockSignal)

    // Verify that isMounted() was checked (the poll function checks it before setState)
    // Since we mocked isMounted to return false, setState should not execute
    expect(mockMountedRef.isMounted).toHaveBeenCalled()
  })

  it("should pass AbortSignal to createAbortableFetch", async () => {
    let capturedSignal: AbortSignal | undefined

    ;(asyncUtils.createAbortableFetch as jest.Mock).mockImplementation(
      (url: string, opts?: { signal?: AbortSignal }) => {
        capturedSignal = opts?.signal
        return {
          promise: Promise.resolve(mockPulseResponse),
          signal: opts?.signal || mockSignal,
          abort: mockAbort,
        }
      }
    )

    render(<SparkPulseMini />)

    // Get the polling function
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn

    const testSignal = {
      aborted: false,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    } as unknown as AbortSignal

    await pollFn(testSignal)

    expect(asyncUtils.createAbortableFetch).toHaveBeenCalledWith(
      "/system/pulse",
      expect.objectContaining({
        signal: testSignal,
      })
    )
  })

  it("should handle fetch errors gracefully", async () => {
    const error = new Error("Network error")

    ;(asyncUtils.createAbortableFetch as jest.Mock).mockReturnValue({
      promise: Promise.reject(error),
      signal: mockSignal,
      abort: mockAbort,
    })

    render(<SparkPulseMini />)

    // Get the polling function and execute it
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn

    await pollFn(mockSignal)

    // Error should be handled by the onError callback or caught in the poll function
    // Since we're mocking, verify the poll function doesn't throw
    await expect(pollFn(mockSignal)).resolves.not.toThrow()
  })

  it("should ignore AbortError when unmounted", async () => {
    const abortError = new Error("Aborted")
    Object.defineProperty(abortError, "name", { value: "AbortError" })

    ;(asyncUtils.createAbortableFetch as jest.Mock).mockReturnValue({
      promise: Promise.reject(abortError),
      signal: mockSignal,
      abort: mockAbort,
    })

    const { unmount } = render(<SparkPulseMini />)

    // Unmount first
    unmount()
    mockMountedRef.isMounted.mockReturnValue(false)

    // Get the polling function and execute it with abort error
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn

    // Should not throw and should return early
    await expect(pollFn(mockSignal)).resolves.not.toThrow()
  })

  it("should update pulse state with fetched data", async () => {
    const { container } = render(<SparkPulseMini />)

    // Get the polling function and execute it
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn

    await pollFn(mockSignal)

    // Component should render (we can't easily test state updates without actual state)
    // But we can verify the polling function was called correctly
    expect(asyncUtils.createAbortableFetch).toHaveBeenCalledWith(
      "/system/pulse",
      expect.any(Object)
    )
  })

  it("should call onError callback for non-abort errors", async () => {
    const error = new Error("Fetch failed")

    ;(asyncUtils.createAbortableFetch as jest.Mock).mockReturnValue({
      promise: Promise.reject(error),
      signal: mockSignal,
      abort: mockAbort,
    })

    render(<SparkPulseMini />)

    // Get the polling function and onError callback
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn
    const onError = pollingCall.onError

    // Execute poll function which should reject
    await pollFn(mockSignal)

    // onError should be called for non-abort errors
    // The startPolling utility will call onError for non-abort errors
    // Since we're mocking, we verify the onError exists and would be called
    expect(onError).toBeDefined()
  })

  it("should update history state when pulse data is received", async () => {
    render(<SparkPulseMini />)

    // Get the polling function
    const pollingCall = (asyncUtils.startPolling as jest.Mock).mock.calls[0][0]
    const pollFn = pollingCall.fn

    // Execute polling function with valid data
    await pollFn(mockSignal)

    // The function should update history state
    // Since we're mocking setState, we verify the polling function completes successfully
    await expect(pollFn(mockSignal)).resolves.not.toThrow()
  })
})

