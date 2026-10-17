from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    source: str                 # 'bilibili' | 'tmdb'
    remote_id: str
    title: str
    subtitle: str = ""
    poster_url: Optional[str] = None
    media: Optional[str] = None  # tmdb: 'movie' | 'tv'
    type_guess: str = "Anime"
    extra: dict = field(default_factory=dict)


class SourceError(Exception):
    """Error yang pesannya aman ditampilkan ke pengguna."""
