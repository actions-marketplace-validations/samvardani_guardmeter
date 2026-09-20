"""Experimental: LLM-as-judge — verdict schema, prompts, and judge implementations.

This subpackage is experimental. It requires external API keys (Anthropic or
OpenAI), makes live network calls, and has low automated test coverage. Treat
its verdicts as advisory, not as ground truth, and pin/verify behaviour before
relying on it in CI.
"""
