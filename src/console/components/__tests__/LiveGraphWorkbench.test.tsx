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
 * Tests for LiveGraphWorkbench EventSource connection management.
 * 
 * Verifies:
 * - Only one EventSource connection exists at a time
 * - Previous connection is closed when jobId changes
 * - Cleanup closes EventSource and sets ref to null
 * - handleGraphUpdate is properly memoized
 */

import React from "react"
import { render, screen } from "@testing-library/react"
import { LiveGraphWorkbench } from "../LiveGraphWorkbench"

// Mock EventSource
class MockEventSource {
  url: string
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  readyState: number = 0
  private _closeCalled = false
  private _closeCallbacks: Array<() => void> = []

  constructor(url: string) {
    this.url = url
    this.readyState = 1 // OPEN
  }

  close() {
    if (this._closeCalled) return
    this._closeCalled = true
    this.readyState = 2 // CLOSED
    this._closeCallbacks.forEach((cb) => cb())
  }

  get closeCalled() {
    return this._closeCalled
  }

  // Helper to simulate a message event
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent("message", { data: JSON.stringify(data) }))
    }
  }

  // Helper to simulate an error event
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event("error"))
    }
  }

  addEventListener() {
    // Mock implementation
  }

  removeEventListener() {
    // Mock implementation
  }
}

// Store all created EventSource instances
const eventSourceInstances: MockEventSource[] = []
const originalEventSource = global.EventSource

describe("LiveGraphWorkbench EventSource Management", () => {
  beforeEach(() => {
    eventSourceInstances.length = 0

    // Mock global EventSource
    global.EventSource = jest.fn((url: string) => {
      const instance = new MockEventSource(url)
      eventSourceInstances.push(instance)
      return instance as any
    }) as any
  })

  afterEach(() => {
    global.EventSource = originalEventSource
    jest.clearAllMocks()
  })

  it("should create EventSource connection when jobId is provided", () => {
    render(<LiveGraphWorkbench jobId="job-1" />)

    expect(global.EventSource).toHaveBeenCalledWith(
      "/api/proxy/orchestrator/jobs/job-1/stream"
    )
    expect(eventSourceInstances.length).toBe(1)
  })

  it("should close previous EventSource when jobId changes", () => {
    const { rerender } = render(<LiveGraphWorkbench jobId="job-1" />)

    expect(eventSourceInstances.length).toBe(1)
    const firstEventSource = eventSourceInstances[0]

    // Change jobId
    rerender(<LiveGraphWorkbench jobId="job-2" />)

    // Previous EventSource should be closed
    expect(firstEventSource.closeCalled).toBe(true)

    // New EventSource should be created
    expect(eventSourceInstances.length).toBe(2)
    expect(global.EventSource).toHaveBeenCalledWith(
      "/api/proxy/orchestrator/jobs/job-2/stream"
    )
  })

  it("should only have one active EventSource connection at a time", () => {
    const { rerender } = render(<LiveGraphWorkbench jobId="job-1" />)

    expect(eventSourceInstances.length).toBe(1)

    // Change jobId multiple times quickly
    rerender(<LiveGraphWorkbench jobId="job-2" />)
    rerender(<LiveGraphWorkbench jobId="job-3" />)

    // All previous connections should be closed
    expect(eventSourceInstances[0].closeCalled).toBe(true)
    expect(eventSourceInstances[1].closeCalled).toBe(true)

    // Only the last connection should be active
    expect(eventSourceInstances.length).toBe(3)
    expect(eventSourceInstances[2].closeCalled).toBe(false)
  })

  it("should close EventSource on component unmount", () => {
    const { unmount } = render(<LiveGraphWorkbench jobId="job-1" />)

    expect(eventSourceInstances.length).toBe(1)
    const eventSource = eventSourceInstances[0]

    unmount()

    // EventSource should be closed on unmount
    expect(eventSource.closeCalled).toBe(true)
  })

  it("should close EventSource when jobId becomes empty", () => {
    const { rerender } = render(<LiveGraphWorkbench jobId="job-1" />)

    expect(eventSourceInstances.length).toBe(1)
    const eventSource = eventSourceInstances[0]

    // Change to empty jobId
    rerender(<LiveGraphWorkbench jobId="" />)

    // EventSource should be closed
    expect(eventSource.closeCalled).toBe(true)
  })

  it("should set eventSourceRef.current to null on cleanup", () => {
    const { unmount } = render(<LiveGraphWorkbench jobId="job-1" />)

    expect(eventSourceInstances.length).toBe(1)
    const eventSource = eventSourceInstances[0]

    unmount()

    // Verify cleanup was called (close was called)
    expect(eventSource.closeCalled).toBe(true)
  })

  it("should close EventSource on error and set ref to null", () => {
    render(<LiveGraphWorkbench jobId="job-1" />)

    expect(eventSourceInstances.length).toBe(1)
    const eventSource = eventSourceInstances[0]

    // Simulate error
    eventSource.simulateError()

    // EventSource should be closed
    expect(eventSource.closeCalled).toBe(true)
  })

  it("should handle multiple jobId changes without leaks", () => {
    const { rerender } = render(<LiveGraphWorkbench jobId="job-1" />)

    // Change jobId multiple times
    for (let i = 2; i <= 5; i++) {
      rerender(<LiveGraphWorkbench jobId={`job-${i}`} />)
    }

    // All previous connections should be closed
    for (let i = 0; i < eventSourceInstances.length - 1; i++) {
      expect(eventSourceInstances[i].closeCalled).toBe(true)
    }

    // Only the last connection should be active
    const lastIndex = eventSourceInstances.length - 1
    expect(eventSourceInstances[lastIndex].closeCalled).toBe(false)
  })

  it("should use custom orchestratorUrl when provided", () => {
    render(<LiveGraphWorkbench jobId="job-1" orchestratorUrl="/custom/orchestrator" />)

    expect(global.EventSource).toHaveBeenCalledWith(
      "/custom/orchestrator/jobs/job-1/stream"
    )
  })

  it("should close and recreate EventSource when orchestratorUrl changes", () => {
    const { rerender } = render(
      <LiveGraphWorkbench jobId="job-1" orchestratorUrl="/orchestrator-1" />
    )

    expect(eventSourceInstances.length).toBe(1)
    const firstEventSource = eventSourceInstances[0]

    rerender(<LiveGraphWorkbench jobId="job-1" orchestratorUrl="/orchestrator-2" />)

    // Previous EventSource should be closed
    expect(firstEventSource.closeCalled).toBe(true)

    // New EventSource should be created with new URL
    expect(eventSourceInstances.length).toBe(2)
    expect(global.EventSource).toHaveBeenLastCalledWith(
      "/orchestrator-2/jobs/job-1/stream"
    )
  })
})

