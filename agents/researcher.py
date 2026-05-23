from typing import TYPE_CHECKING
import re
import yt_dlp
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from agents.graph import GraphState

MODEL = "gemini-3.1-flash-lite-preview"

class ResearcherResult(BaseModel):
    """Structured result from the Researcher agent."""
    youtube_url: str = Field(description="The URL of the official YouTube video/audio.")
    title: str = Field(description="The title of the track.")
    artist: str = Field(description="The artist of the track.")
    slug: str = Field(description="A URL-safe slugified version of track_id (e.g. 'humble_kendrick_lamar').")
    reasoning: str = Field(description="Brief explanation of why this link was chosen.")

from urllib.parse import urlparse, parse_qs

def _clean_youtube_url(url: str) -> str:
    """Canonical https://www.youtube.com/watch?v=<id>.
    Strips radio/mix/playlist/tracking params that make yt-dlp (and the
    MCP server's downloader) fail. Returns input unchanged if no id found."""
    if not url:
        return url
    try:
        p = urlparse(url.strip())
        host = p.netloc.lower()
        vid = None
        if "youtu.be" in host:
            vid = p.path.lstrip("/").split("/")[0]
        elif "youtube.com" in host:
            vid = (parse_qs(p.query).get("v") or [None])[0]
            if not vid and "/shorts/" in p.path:
                vid = p.path.split("/shorts/")[1].split("/")[0]
            if not vid and "/embed/" in p.path:
                vid = p.path.split("/embed/")[1].split("/")[0]
        return f"https://www.youtube.com/watch?v={vid}" if vid else url
    except Exception:
        return url

def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

def researcher_node(state: "GraphState") -> "GraphState":
    """
    Researcher node: Takes user_input and finds the official YouTube URL using yt-dlp.
    """
    user_input = state.get("user_input", "")
    if not user_input:
        return {**state, "error": "No user input provided to Researcher."}

    # Clean the input if it's a YouTube URL
    cleaned_input = _clean_youtube_url(user_input)

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'default_search': 'ytsearch3',
        'socket_timeout': 10,  # 10s socket timeout
    }
    
    search_results = []
    search_error = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # If input is a non-YouTube URL, force a search instead of extracting to avoid DRM issues
            search_query = cleaned_input
            if cleaned_input.startswith("http") and "youtube.com" not in cleaned_input and "youtu.be" not in cleaned_input:
                search_query = f"ytsearch3:{cleaned_input}"
                
            info = ydl.extract_info(search_query, download=False)
            
            entries = info.get('entries', [info])
            for entry in entries:
                if not entry: continue
                search_results.append({
                    "title": entry.get("title"),
                    "url": entry.get("url") or entry.get("webpage_url"),
                    "channel": entry.get("uploader") or entry.get("channel"),
                    "is_verified": entry.get("channel_is_verified"),
                    "duration": entry.get("duration")
                })
    except Exception as e:
        search_error = str(e)
        print(f"yt-dlp warning: {search_error}")

    # Fail loud if no search results found, preventing LLM hallucinations
    if not search_results:
        err_msg = "yt-dlp failed to find any search results."
        if search_error:
            err_msg += f" Details: {search_error}"
        return {**state, "error": err_msg}

    llm = ChatGoogleGenerativeAI(model=MODEL, temperature=0, timeout=30.0)
    
    system_prompt = (
        "You are an expert music researcher. Your goal is to find the OFFICIAL YouTube link for a given song or link from the search results provided. "
        "PRIORITY: \n"
        "1. Official Audio / Topic Channel Audio\n"
        "2. Lyric Video (from Official Artist Channel)\n"
        "3. Music Video (from Official Artist Channel)\n\n"
        "STRICT RULE: Only select links from Official Artist Channels or 'Topic' channels. "
        "Check the 'channel' and 'is_verified' fields. Ignore fan uploads, covers, or unofficial lyric videos.\n\n"
        "Return the result by calling the ResearcherResult tool."
    )
    
    human_prompt = (
        f"User Input: {user_input}\n\n"
        f"Search Results:\n{search_results}\n\n"
        "Identify the official track details and provide the best YouTube URL."
    )

    llm_with_tool = llm.bind_tools([ResearcherResult], tool_choice="ResearcherResult")
    response = llm_with_tool.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    try:
        tool_call = response.tool_calls[0]
        result = ResearcherResult.model_validate(tool_call["args"])
        
        # Canonicalize the final chosen YouTube URL before saving
        final_youtube_url = _clean_youtube_url(result.youtube_url)
        
        return {
            **state,
            "youtube_url": final_youtube_url,
            "researcher_metadata": {
                "title": result.title,
                "artist": result.artist,
                "slug": result.slug,
                "reasoning": result.reasoning
            }
        }
    except Exception as e:
        return {**state, "error": f"Researcher failed to parse results: {str(e)}"}
