import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from agents.researcher import _clean_youtube_url, researcher_node

# ── Clean YouTube URL Unit Tests ──────────────────────────────────────────────

def test_clean_youtube_url_standard():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert _clean_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

def test_clean_youtube_url_with_tracking_and_playlist():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=123456&list=RDdQw4w9WgXcQ&index=1"
    assert _clean_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

def test_clean_youtube_url_short():
    url = "https://youtu.be/dQw4w9WgXcQ?si=789"
    assert _clean_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

def test_clean_youtube_url_shorts():
    url = "https://www.youtube.com/shorts/dQw4w9WgXcQ?si=abc"
    assert _clean_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

def test_clean_youtube_url_embed():
    url = "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1"
    assert _clean_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

def test_clean_youtube_url_idempotent_for_non_youtube():
    url = "blinding lights the weeknd"
    assert _clean_youtube_url(url) == url

def test_clean_youtube_url_none():
    assert _clean_youtube_url(None) is None
    assert _clean_youtube_url("") == ""

# ── Researcher Node Mock Tests ───────────────────────────────────────────────

@patch("agents.researcher.yt_dlp.YoutubeDL")
def test_researcher_node_fails_loud_on_empty_search(mock_ytdl_class):
    # Setup mock to return no entries/results
    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {"entries": []}
    mock_ytdl_class.return_value.__enter__.return_value = mock_instance

    state = {
        "user_input": "blinding lights the weeknd",
        "error": None
    }
    result = researcher_node(state)
    assert result["error"] is not None
    assert "yt-dlp failed to find any search results" in result["error"]


@patch("agents.researcher.ChatGoogleGenerativeAI")
@patch("agents.researcher.yt_dlp.YoutubeDL")
def test_researcher_node_success(mock_ytdl_class, mock_chat_class):
    # Setup mock yt-dlp to return one valid search result
    mock_ytdl_instance = MagicMock()
    mock_ytdl_instance.extract_info.return_value = {
        "entries": [
            {
                "title": "The Weeknd - Blinding Lights (Official Audio)",
                "url": "https://www.youtube.com/watch?v=4NRXx6U8ABQ&si=123",
                "uploader": "The Weeknd Topic",
                "channel_is_verified": True,
                "duration": 200
            }
        ]
    }
    mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl_instance

    # Setup mock ChatGoogleGenerativeAI and its bound tools
    mock_response = MagicMock()
    mock_response.tool_calls = [
        {
            "args": {
                "youtube_url": "https://www.youtube.com/watch?v=4NRXx6U8ABQ&si=123",
                "title": "Blinding Lights",
                "artist": "The Weeknd",
                "slug": "blinding_lights_weeknd",
                "reasoning": "Official topic channel link selected."
            }
        }
    ]
    
    mock_llm_instance = MagicMock()
    mock_llm_instance.invoke.return_value = mock_response
    
    # bind_tools returns a mock LLM that actually gets invoked
    mock_chat_class.return_value.bind_tools.return_value = mock_llm_instance

    state = {
        "user_input": "blinding lights",
        "error": None
    }
    
    result = researcher_node(state)
    
    assert result.get("error") is None
    assert result["youtube_url"] == "https://www.youtube.com/watch?v=4NRXx6U8ABQ"
    assert result["researcher_metadata"]["title"] == "Blinding Lights"
    assert result["researcher_metadata"]["artist"] == "The Weeknd"
    assert result["researcher_metadata"]["slug"] == "blinding_lights_weeknd"
