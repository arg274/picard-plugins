# -*- coding: utf-8 -*-

from picard import config, log
from picard.util import LockableObject
from picard.metadata import register_track_metadata_processor
from functools import partial


PLUGIN_NAME = 'Album Artist Area'
PLUGIN_AUTHOR = 'Sophist, Sambhav Kothari, snobdiggy'
PLUGIN_DESCRIPTION = '''Add's the album artist(s) area
(if they are defined in the MusicBrainz database).'''
PLUGIN_VERSION = '0.2'
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


# noinspection PyProtectedMember
class AlbumArtistArea:
    class ArtistQueue(LockableObject):

        def __init__(self):
            LockableObject.__init__(self)
            self.queue = {}

        def __contains__(self, name):
            return name in self.queue

        def __iter__(self):
            return self.queue.__iter__()

        def __getitem__(self, name):
            self.lock_for_read()
            value = self.queue[name] if name in self.queue else None
            self.unlock()
            return value

        def __setitem__(self, name, value):
            self.lock_for_write()
            self.queue[name] = value
            self.unlock()

        def append(self, name, value):
            self.lock_for_write()
            if name in self.queue:
                self.queue[name].append(value)
                value = False
            else:
                self.queue[name] = [value]
                value = True
            self.unlock()
            return value

        def remove(self, name):
            self.lock_for_write()
            value = None
            if name in self.queue:
                value = self.queue[name]
                del self.queue[name]
            self.unlock()
            return value

    class AreaQueue(ArtistQueue):
        pass

    def __init__(self):
        self.area_cache = {}
        self.artist_queue = self.ArtistQueue()
        self.area_queue = self.AreaQueue()

    def add_artist_area(self, tagger, track_metadata, track_node, release_node):
        areas = set()
        album_artist_ids = track_metadata.getall('musicbrainz_albumartistid')

        for album_artist_id in album_artist_ids:
            if album_artist_id in self.area_cache:
                if self.area_cache[album_artist_id]:
                    track_metadata['artistarea'] = self.area_cache[album_artist_id]
            else:
                self.make_request_artist(tagger, tagger._new_tracks[-1], album_artist_id)

    def make_request_artist(self, tagger, track, artist_id):
        tagger._requests += 1
        if self.artist_queue.append(artist_id, (track, tagger)):
            host = config.setting["server_host"]
            port = config.setting["server_port"]
            path = "/ws/2/%s/%s" % ('artist', artist_id)
            queryargs = {"fmt": "json"}
            return tagger.tagger.webservice.get(host, port, path,
                                                partial(self.artist_process, tagger, artist_id),
                                                parse_response_type="json", priority=True, important=False,
                                                queryargs=queryargs)

    def make_request_area(self, tagger, artist_id, area_id):
        host = config.setting["server_host"]
        port = config.setting["server_port"]
        path = "/ws/2/%s/%s" % ('area', area_id)
        queryargs = {"fmt": "json",
                     "inc": "area-rels"}
        return tagger.tagger.webservice.get(host, port, path,
                                            partial(self.area_process, tagger, artist_id, area_id),
                                            parse_response_type="json", priority=True, important=False,
                                            queryargs=queryargs)

    def artist_process(self, tagger, artist_id, response, reply, error):
        if error:
            log.error("%s: %r: Network error retrieving artist record", PLUGIN_NAME, artist_id)
            tuples = self.artist_queue.remove(artist_id)
            for track, tagger in tuples:
                tagger._requests -= 1
                tagger._finalize_loading(None)
            return

        area_id = self.artist_parse_response(response)
        self.make_request_area(tagger, artist_id, area_id)

        log.debug("%s: %r: Response = %s", PLUGIN_NAME, artist_id, area_id)

    @staticmethod
    def artist_parse_response(response):
        try:
            area_id = response['area']['id']
            return area_id
        except KeyError:
            return None

    def area_process(self, tagger, artist_id, area_id, response, reply, error):
        if error:
            log.error("%s: %r: Network error retrieving area record", PLUGIN_NAME, area_id)
            tagger._requests -= 1
            tagger._finalize_loading(None)
            return

        area_name, prev_id = self.area_parse_response(response)
        log.debug("%s: %r: Response = %s %s", PLUGIN_NAME, area_id, area_name, prev_id)

        if prev_id is not None:
            self.make_request_area(tagger, artist_id, prev_id)
        else:
            self.area_cache[artist_id] = area_name
            tuples = self.artist_queue.remove(artist_id)
            for track, tagger in tuples:
                if area_name:
                    tm = track.metadata
                    tm['artistarea'] = area_name
                    for file in track.iterfiles(True):
                        fm = file.metadata
                        fm['artistarea'] = area_name

                tagger._requests -= 1
                tagger._finalize_loading(None)

        tagger._requests -= 1
        tagger._finalize_loading(None)

    @staticmethod
    def area_parse_response(response):
        try:
            prev_id = None
            if response['type'] != 'Country':
                for entry in response['relations']:
                    if entry['direction'] == 'backward':
                        prev_id = entry['area']['id']
                        break
            return response['name'], prev_id
        except KeyError:
            return None, None


register_track_metadata_processor(AlbumArtistArea().add_artist_area)
