"""Điều phối: rewrite → retrieve → rerank → (web fallback nếu không đủ ngữ cảnh) → generate. Phát Event cho /chat và /chat/stream.

Phụ trách: TV3 · [S3] Generation: prompt + trích dẫn + llm.py
"""
