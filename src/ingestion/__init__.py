"""Ingestion module for extracting knowledge graphs from text."""

from .extractor import KnowledgeExtractor, extract_knowledge_graph, extract_pact_graph

__all__ = ["KnowledgeExtractor", "extract_knowledge_graph", "extract_pact_graph"]  # extract_pact_graph is deprecated

