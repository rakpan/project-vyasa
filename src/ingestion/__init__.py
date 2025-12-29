"""Ingestion module for extracting PACT ontology from text."""

from .extractor import PACTExtractor, extract_pact_graph

__all__ = ["PACTExtractor", "extract_pact_graph"]

