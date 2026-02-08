#!/usr/bin/env python3
"""Verify configuration and re-ingest with new chunk size."""

import sys
sys.path.insert(0, '.')

from config import Config

print("="*60)
print("Configuration Verification")
print("="*60)
print(f"CHUNK_SIZE: {Config.CHUNK_SIZE} tokens")
print(f"CHUNK_OVERLAP: {Config.CHUNK_OVERLAP} tokens")
print(f"Expected chunk size: ~{Config.CHUNK_SIZE * 4} characters")
print(f"Expected # of chunks: 200-300+ (was 45)")
print("="*60)
print()
print("If configuration is correct, run:")
print("  python main.py")
print()
print("Expected results:")
print("  - FAISS index with 200+ vectors")
print("  - Average chunk size ~1000 characters")
print("  - More specific retrieval results")
