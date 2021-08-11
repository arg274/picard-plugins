from abc import ABC, abstractmethod


class LyricsAPI(ABC):

    @abstractmethod
    def set_auth(self, payload=None):
        pass

    @abstractmethod
    def get_lyrics_id(self, track_id):
        pass

    @abstractmethod
    def get_lyrics_isrc(self, isrc):
        pass

    @abstractmethod
    def parse_lyrics(self, lyrics):
        pass
