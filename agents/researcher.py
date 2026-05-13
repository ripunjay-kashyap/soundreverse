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

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'default_search': 'ytsearch3',
    }
    
    search_results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # If input is a non-YouTube URL, force a search instead of extracting to avoid DRM issues
            search_query = user_input
            if user_input.startswith("http") and "youtube.com" not in user_input and "youtu.be" not in user_input:
                search_query = f"ytsearch3:{user_input}"
                
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
        print(f"yt-dlp warning: {str(e)}")

    llm = ChatGoogleGenerativeAI(model=MODEL, temperature=0)
    
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
        
        return {
            **state,
            "youtube_url": result.youtube_url,
            "researcher_metadata": {
                "title": result.title,
                "artist": result.artist,
                "slug": result.slug,
                "reasoning": result.reasoning
            }
        }
    except Exception as e:
        return {**state, "error": f"Researcher failed to parse results: {str(e)}"}
