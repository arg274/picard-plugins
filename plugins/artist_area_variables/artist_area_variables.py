# -*- coding: utf-8 -*-

from picard import config, log
from picard.util import LockableObject
from picard.metadata import register_track_metadata_processor
from functools import partial


PLUGIN_NAME = 'Album Artist Area'
PLUGIN_AUTHOR = 'Sophist, Sambhav Kothari, snobdiggy'
PLUGIN_DESCRIPTION = '''Add's the album artist(s) area
(if they are defined in the MusicBrainz database).'''
PLUGIN_VERSION = '0.2.1'
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

    class AreaList:
        class Area:
            def __init__(self, area_id, area_name, parent_id):
                self.area_id = area_id
                self.name = area_name
                self.parent_id = parent_id

        def __init__(self):
            self.areas = []

        def add(self, area):
            if area.area_id is not None and area not in self.areas:
                self.areas.append(area)

        def get(self):
            innermost_area = None
            outermost_area = None
            if self.areas:
                outermost_area = self.areas[-1].name
                innermost_area = self.areas[0].name if len(self.areas) > 1 else None
            return innermost_area, outermost_area

    def __init__(self):
        self.area_cache = {}
        self.artist_queue = self.ArtistQueue()
        self.area_queue = self.AreaQueue()
        self.area_list = self.AreaList()

    def add_artist_area(self, tagger, track_metadata, track_node, release_node):
        areas = set()
        album_artist_ids = track_metadata.getall('musicbrainz_albumartistid')

        for album_artist_id in album_artist_ids:
            if album_artist_id in self.area_cache:
                if self.area_cache[album_artist_id]:
                    track_metadata['artistarea'], track_metadata['artistcountry']\
                        = self.area_cache[album_artist_id]
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

        area = self.area_parse_response(response)
        log.debug("%s: %r: Response = %s %s", PLUGIN_NAME, area_id, area.name, area.parent_id)
        self.area_list.add(area)

        if area.parent_id is not None:
            self.make_request_area(tagger, artist_id, area.parent_id)
        else:
            innermost_area, outermost_area = self.area_list.get()
            log.debug("%s: innermost: %s, outermost: %s", PLUGIN_NAME, innermost_area, outermost_area)
            self.area_cache[artist_id] = (innermost_area, outermost_area)
            tuples = self.artist_queue.remove(artist_id)
            for track, tagger in tuples:
                if innermost_area:
                    tm = track.metadata
                    tm['artistarea'] = innermost_area
                    for file in track.iterfiles(True):
                        fm = file.metadata
                        fm['artistarea'] = innermost_area
                if outermost_area:
                    tm = track.metadata
                    tm['artistcountry'] = outermost_area
                    for file in track.iterfiles(True):
                        fm = file.metadata
                        fm['artistcountry'] = outermost_area

                tagger._requests -= 1
                tagger._finalize_loading(None)

        tagger._requests -= 1
        tagger._finalize_loading(None)

    def area_parse_response(self, response):
        try:
            parent_id = None
            if response['type'] != 'Country':
                for entry in response['relations']:
                    if entry['direction'] == 'backward':
                        parent_id = entry['area']['id']
                        break
            return self.AreaList.Area(response['id'], response['name'], parent_id)
        except KeyError:
            return self.AreaList.Area(None, None, None)


register_track_metadata_processor(AlbumArtistArea().add_artist_area)
