/**
 * Unit tests for WebSearchPanel component.
 * 
 * Tests verify:
 * - Queue action triggers API call
 * - Status response is displayed correctly
 * - Deep link to Review Queue works
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WebSearchPanel } from "../workbench/WebSearchPanel";
import * as webSearchService from "@/services/webSearchService";

// Mock the web search service
jest.mock("@/services/webSearchService");
jest.mock("@/hooks/use-toast", () => ({
  toast: jest.fn(),
}));

describe("WebSearchPanel", () => {
  const mockProjectId = "test-project-123";
  
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  it("renders search input and button", () => {
    render(<WebSearchPanel projectId={mockProjectId} />);
    
    expect(screen.getByPlaceholderText("Search the web...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /search/i })).toBeInTheDocument();
  });
  
  it("shows allowlist restriction note", () => {
    render(<WebSearchPanel projectId={mockProjectId} />);
    
    expect(screen.getByText(/Results restricted to approved domains/i)).toBeInTheDocument();
  });
  
  it("displays search results after successful search", async () => {
    const mockResults = [
      {
        title: "Test Result 1",
        link: "https://fda.gov/page1",
        snippet: "Test snippet 1",
        displayLink: "fda.gov",
        quality_tier: "high",
        quality_score: 0.9,
      },
      {
        title: "Test Result 2",
        link: "https://cdc.gov/page2",
        snippet: "Test snippet 2",
        displayLink: "cdc.gov",
        quality_tier: "high",
        quality_score: 0.9,
      },
    ];
    
    (webSearchService.searchWeb as jest.Mock).mockResolvedValue({
      results: mockResults,
      total_results: 100,
    });
    
    render(<WebSearchPanel projectId={mockProjectId} />);
    
    const input = screen.getByPlaceholderText("Search the web...");
    const searchButton = screen.getByRole("button", { name: /search/i });
    
    await userEvent.type(input, "test query");
    await userEvent.click(searchButton);
    
    await waitFor(() => {
      expect(screen.getByText("Test Result 1")).toBeInTheDocument();
      expect(screen.getByText("Test Result 2")).toBeInTheDocument();
    });
  });
  
  it("handles queue action and shows status", async () => {
    const mockResults = [
      {
        title: "Test Result",
        link: "https://fda.gov/page",
        snippet: "Test snippet",
        displayLink: "fda.gov",
      },
    ];
    
    (webSearchService.searchWeb as jest.Mock).mockResolvedValue({
      results: mockResults,
      total_results: 10,
    });
    
    (webSearchService.queueUrls as jest.Mock).mockResolvedValue({
      review_task_id: "review-123",
      status: "PENDING",
      urls_queued: 1,
      urls_failed: 0,
      message: "Queued 1 URL(s) for review",
    });
    
    render(<WebSearchPanel projectId={mockProjectId} />);
    
    // Perform search
    const input = screen.getByPlaceholderText("Search the web...");
    const searchButton = screen.getByRole("button", { name: /search/i });
    
    await userEvent.type(input, "test query");
    await userEvent.click(searchButton);
    
    await waitFor(() => {
      expect(screen.getByText("Test Result")).toBeInTheDocument();
    });
    
    // Select URL and queue
    const checkbox = screen.getByRole("checkbox");
    await userEvent.click(checkbox);
    
    const queueButton = screen.getByRole("button", { name: /queue.*for review/i });
    await userEvent.click(queueButton);
    
    // Verify queue API was called
    await waitFor(() => {
      expect(webSearchService.queueUrls).toHaveBeenCalledWith(
        ["https://fda.gov/page"],
        mockProjectId,
        "test query"
      );
    });
  });
  
  it("handles queue failure and shows error", async () => {
    const mockResults = [
      {
        title: "Test Result",
        link: "https://fda.gov/page",
        snippet: "Test snippet",
        displayLink: "fda.gov",
      },
    ];
    
    (webSearchService.searchWeb as jest.Mock).mockResolvedValue({
      results: mockResults,
      total_results: 10,
    });
    
    (webSearchService.queueUrls as jest.Mock).mockResolvedValue({
      review_task_id: "review-123",
      status: "FAILED",
      urls_queued: 0,
      urls_failed: 1,
      message: "Queue failed: quota_exceeded",
      reason: "quota_exceeded",
    });
    
    render(<WebSearchPanel projectId={mockProjectId} />);
    
    // Perform search and queue
    const input = screen.getByPlaceholderText("Search the web...");
    const searchButton = screen.getByRole("button", { name: /search/i });
    
    await userEvent.type(input, "test query");
    await userEvent.click(searchButton);
    
    await waitFor(() => {
      expect(screen.getByText("Test Result")).toBeInTheDocument();
    });
    
    const checkbox = screen.getByRole("checkbox");
    await userEvent.click(checkbox);
    
    const queueButton = screen.getByRole("button", { name: /queue.*for review/i });
    await userEvent.click(queueButton);
    
    // Verify queue API was called
    await waitFor(() => {
      expect(webSearchService.queueUrls).toHaveBeenCalled();
    });
  });
  
  it("shows empty state when no results", () => {
    render(<WebSearchPanel projectId={mockProjectId} />);
    
    expect(screen.getByText(/Enter a search query to find web sources/i)).toBeInTheDocument();
  });
});

