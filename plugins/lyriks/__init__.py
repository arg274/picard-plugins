from functools import partial

from picard import log
from picard.metadata import register_track_metadata_processor
from picard.util import thread

from .deezerapi import DeezerAPI

PLUGIN_NAME = 'Lyriks'
PLUGIN_AUTHOR = 'snobdiggy'
PLUGIN_DESCRIPTION = '''Multi-source lyrics seeder for Picard.'''
PLUGIN_VERSION = '0.1.0'
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


class Lyriks:

    def __init__(self):
        self.deez_api = DeezerAPI.get_instance()

    def process_lyrics(self, tagger, track_metadata, track_node, release_node):
        thread.run_task(
            partial(self.fetch_lyrics, tagger, track_metadata),
            partial(self.apply_lyrics, tagger, track_metadata)
        )

    def fetch_lyrics(self, tagger, track_metadata):
        if track_metadata:
            isrcs = track_metadata.getall('isrc')
            for isrc in isrcs:
                tagger._requests += 1
                lyrics = self.deez_api.get_lyrics_isrc(isrc)
                track_metadata['lyrics'] = lyrics
                log.debug("%s: ISRC: %s, lyrics = %s", PLUGIN_NAME, isrc, lyrics)
                return lyrics
        return None

    @staticmethod
    def apply_lyrics(tagger, track_metadata, result=None, error=None):
        if error:
            return
        else:
            track_metadata['lyrics'] = result
        tagger._requests -= 1
        tagger._finalize_loading(None)


register_track_metadata_processor(Lyriks().process_lyrics)
