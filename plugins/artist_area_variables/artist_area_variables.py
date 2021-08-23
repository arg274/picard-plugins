# -*- coding: utf-8 -*-

from picard import config, log
from picard.util import LockableObject
from picard.metadata import register_track_metadata_processor
from functools import partial

PLUGIN_NAME = 'Album Artist Area'
PLUGIN_AUTHOR = 'snobdiggy, Sophist, Sambhav Kothari'
PLUGIN_DESCRIPTION = '''Add's the album artist(s) area
(if they are defined in the MusicBrainz database).'''
PLUGIN_VERSION = '0.3.1'
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

    class AreaList:
        class Area:
            def __init__(self, area_id, area_name, parent_id):
                self.area_id = area_id
                self.name = area_name
                self.parent_id = parent_id

            def __eq__(self, other):
                if not isinstance(other, AlbumArtistArea.AreaList.Area):
                    return NotImplemented
                return self.area_id == other.area_id

            def __str__(self):
                return '{id: {}, name: {}, parent_id: {}}'.format(self.area_id, self.name, self.parent_id)

        def __init__(self):
            self.areas = []

        def add(self, area):
            if area.area_id is not None and area not in self.areas:
                self.areas.append(area)

        def get(self):
            innermost_area_name = None
            outermost_area_name = None
            log.debug("%s: arealist: %s", PLUGIN_NAME, self.areas)
            if self.areas:
                outermost_area = self.areas[-1]
                outermost_area_name = outermost_area.name
                for idx in range(len(self.areas) - 1, 0, -1):
                    if self.areas[idx].area_id != self.areas[idx - 1].parent_id:
                        self.areas[0:idx] = []
                        log.debug("%s: arealist post-delete: %s", PLUGIN_NAME, self.areas)
                        break
                innermost_area = self.areas[0] if self.areas[-1] != self.areas[0] else None
                if innermost_area:
                    innermost_area_name = innermost_area.name
            return innermost_area_name, outermost_area_name

        def clear(self):
            self.areas.clear()

    def __init__(self):
        self.area_cache = {}
        self.artist_queue = self.ArtistQueue()
        self.area_list = self.AreaList()

    @staticmethod
    def populate_as_list(metadata_var, val):
        if not metadata_var:
            if val:
                return [val]
        else:
            log.debug("%s: Metadata var = %s", PLUGIN_NAME, metadata_var)
            if val not in metadata_var:
                if isinstance(metadata_var, str):
                    metadata_var = [metadata_var, val]
                elif isinstance(metadata_var, list):
                    metadata_var.append(val)
            return metadata_var
        return None

    def add_artist_area(self, tagger, track_metadata, track_node, release_node):
        album_artist_ids = track_metadata.getall('musicbrainz_albumartistid')

        for album_artist_id in album_artist_ids:
            if album_artist_id in self.area_cache:
                if self.area_cache[album_artist_id]:
                    track_metadata['artistarea'] = self.populate_as_list(track_metadata['artistarea'],
                                                                         self.area_cache[album_artist_id][0])
                    track_metadata['artistcountry'] = self.populate_as_list(track_metadata['artistcountry'],
                                                                            self.area_cache[album_artist_id][1])
            else:
                try:
                    self.make_request_artist(tagger, tagger._new_tracks[-1], album_artist_id)
                except AttributeError:
                    return

        self.area_list.clear()

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
            log.error("%s: %s: Network error retrieving artist record", PLUGIN_NAME, artist_id)
            tuples = self.artist_queue.remove(artist_id)
            for track, tagger in tuples:
                tagger._requests -= 1
                tagger._finalize_loading(None)
            return

        area_id = self.artist_parse_response(response)
        self.area_list.clear()
        if area_id:
            self.make_request_area(tagger, artist_id, area_id)
        else:
            tuples = self.artist_queue.remove(artist_id)
            for track, tagger in tuples:
                tagger._requests -= 1
                tagger._finalize_loading(None)

        log.debug("%s: %s: Response = %s", PLUGIN_NAME, artist_id, area_id)

    @staticmethod
    def artist_parse_response(response):
        try:
            area_id = response['area']['id']
            return area_id
        except (TypeError, KeyError):
            return None

    def area_process(self, tagger, artist_id, area_id, response, reply, error):
        if error:
            log.error("%s: %s: Network error retrieving area record", PLUGIN_NAME, area_id)
            tagger._requests -= 1
            tagger._finalize_loading(None)
            return

        area = self.area_parse_response(response)
        log.debug("%s: %s: Response = %s %s", PLUGIN_NAME, area_id, area.name, area.parent_id)
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
                    tm['artistarea'] = self.populate_as_list(tm['artistarea'], innermost_area)
                    for file in track.iterfiles(True):
                        fm = file.metadata
                        fm['artistarea'] = self.populate_as_list(fm['artistarea'], innermost_area)
                if outermost_area:
                    tm = track.metadata
                    tm['artistcountry'] = self.populate_as_list(tm['artistcountry'], outermost_area)
                    for file in track.iterfiles(True):
                        fm = file.metadata
                        fm['artistcountry'] = self.populate_as_list(fm['artistcountry'], outermost_area)

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
        except (TypeError, KeyError):
            return self.AreaList.Area(None, None, None)


register_track_metadata_processor(AlbumArtistArea().add_artist_area)
