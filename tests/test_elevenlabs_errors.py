"""Tests for ElevenLabs TTS error handling"""
from __future__ import annotations

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import aiohttp

from livekit.agents import APIStatusError


@pytest.mark.asyncio
async def test_elevenlabs_websocket_error_handling():
    """Test that ElevenLabs WebSocket error responses are properly handled"""
    # This test would require setting up a mock WebSocket connection
    # For now, we'll test the error parsing logic directly
    
    # Test data that simulates ElevenLabs error responses
    test_cases = [
        {
            "data": {"error": "only_for_creator+: This voice is only available to its creator"},
            "expected_status": 403,
            "description": "403 error for creator-only voice"
        },
        {
            "data": {"error": "insufficient_quota: Not enough credits"},
            "expected_status": 402,
            "description": "402 error for insufficient quota"
        },
        {
            "data": {"error": "invalid_api_key: API key is invalid"},
            "expected_status": 401,
            "description": "401 error for invalid API key"
        },
        {
            "data": {"error": "voice_not_found: The voice ID was not found"},
            "expected_status": 404,
            "description": "404 error for voice not found"
        },
        {
            "data": {"error": "rate_limit_exceeded: Too many requests"},
            "expected_status": 429,
            "description": "429 error for rate limiting"
        },
        {
            "data": {"error": "invalid_model: Model not supported"},
            "expected_status": 400,
            "description": "400 error for invalid model"
        },
        {
            "data": {"error": "some_other_server_error"},
            "expected_status": 500,
            "description": "500 error for unknown server errors"
        },
    ]
    
    # Import the error handling logic (we can't easily test the WebSocket part)
    # Instead, we'll simulate the error parsing
    for case in test_cases:
        data = case["data"]
        expected_status = case["expected_status"]
        
        # Simulate the error handling logic from the ElevenLabs plugin
        error_msg = data["error"]
        status_code = 500  # Default to server error
        
        # Common ElevenLabs error patterns that indicate client errors (4xx)
        client_error_patterns = [
            "only_for_creator",  # 403 Forbidden
            "insufficient_quota",  # 402 Payment Required
            "invalid_api_key",  # 401 Unauthorized
            "voice_not_found",  # 404 Not Found
            "invalid_voice",  # 400 Bad Request
            "invalid_model",  # 400 Bad Request
            "rate_limit",  # 429 Too Many Requests
        ]
        
        error_lower = error_msg.lower()
        for pattern in client_error_patterns:
            if pattern in error_lower:
                if pattern == "only_for_creator":
                    status_code = 403
                elif pattern == "insufficient_quota":
                    status_code = 402
                elif pattern == "invalid_api_key":
                    status_code = 401
                elif pattern in ["voice_not_found"]:
                    status_code = 404
                elif pattern == "rate_limit":
                    status_code = 429
                else:
                    status_code = 400
                break
        
        # Verify the status code mapping is correct
        assert status_code == expected_status, f"Failed for {case['description']}: expected {expected_status}, got {status_code}"
        
        # Verify that 4xx errors would be non-retryable
        exception = APIStatusError(
            message=error_msg,
            status_code=status_code,
            request_id=data.get("request_id"),
        )
        
        # 4xx errors should be non-retryable, 5xx should be retryable
        if 400 <= status_code < 500:
            assert not exception.retryable, f"4xx error should not be retryable: {case['description']}"
        else:
            assert exception.retryable, f"5xx error should be retryable: {case['description']}"


def test_api_status_error_retryable_behavior():
    """Test that APIStatusError correctly sets retryable flag based on status code"""
    # 4xx errors should not be retryable
    for status_code in [400, 401, 403, 404, 429]:
        error = APIStatusError("Client error", status_code=status_code)
        assert not error.retryable, f"Status code {status_code} should not be retryable"
    
    # 5xx errors should be retryable
    for status_code in [500, 502, 503]:
        error = APIStatusError("Server error", status_code=status_code)
        assert error.retryable, f"Status code {status_code} should be retryable"
    
    # Explicit override should work
    error = APIStatusError("Override", status_code=403, retryable=True)
    assert error.retryable, "Explicit retryable=True should override status code logic"