# -*- coding: utf-8 -*-

from picard import config, log
from picard.util import LockableObject
from picard.metadata import register_track_metadata_processor
from functools import partial


PLUGIN_NAME = 'Album Artist Area'
PLUGIN_AUTHOR = 'Sophist, Sambhav Kothari, snobdiggy'
PLUGIN_DESCRIPTION = '''Add's the album artist(s) area
(if they are defined in the MusicBrainz database).'''
PLUGIN_VERSION = '0.1.1'
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


class AlbumArtistArea:

    class ArtistAreaQueue(LockableObject):

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

    def __init__(self):
        self.area_cache = {}
        self.area_queue = self.ArtistAreaQueue()

    def add_artist_area(self, album, track_metadata, track_node, release_node):
        album_artist_ids = track_metadata.getall('musicbrainz_albumartistid')
        for artistId in album_artist_ids:
            if artistId in self.area_cache:
                if self.area_cache[artistId]:
                    track_metadata['artistarea'] = self.area_cache[artistId]
            else:
                # Jump through hoops to get track object!!
                # noinspection PyProtectedMember
                self.area_add_track(album, album._new_tracks[-1], artistId)

    def area_add_track(self, album, track, artist_id):
        self.album_add_request(album)
        if self.area_queue.append(artist_id, (track, album)):
            host = config.setting["server_host"]
            port = config.setting["server_port"]
            path = "/ws/2/%s/%s" % ('artist', artist_id)
            queryargs = {"inc": "url-rels"}
            return album.tagger.webservice.get(host, port, path,
                                               partial(self.area_process, artist_id),
                                               parse_response_type="xml", priority=True, important=False,
                                               queryargs=queryargs)

    def area_process(self, artist_id, response, reply, error):
        if error:
            log.error("%s: %r: Network error retrieving artist record", PLUGIN_NAME, artist_id)
            tuples = self.area_queue.remove(artist_id)
            for track, album in tuples:
                self.album_remove_request(album)
            return
        urls = self.artist_process_metadata(artist_id, response)
        self.area_cache[artist_id] = urls
        tuples = self.area_queue.remove(artist_id)
        log.debug("%s: %r: Artist Official Homepages = %r", PLUGIN_NAME,
                  artist_id, urls)
        for track, album in tuples:
            if urls:
                tm = track.metadata
                tm['artistarea'] = urls
                for file in track.iterfiles(True):
                    fm = file.metadata
                    fm['artistarea'] = urls
            self.album_remove_request(album)

    # noinspection PyMethodMayBeStatic
    def album_add_request(self, album):
        # noinspection PyProtectedMember
        album._requests += 1

    # noinspection PyMethodMayBeStatic,PyProtectedMember
    def album_remove_request(self, album):
        album._requests -= 1
        album._finalize_loading(None)

    # noinspection PyMethodMayBeStatic
    def artist_process_metadata(self, artist_id, response):
        if 'metadata' in response.children:
            if 'artist' in response.metadata[0].children:
                if 'area' in response.metadata[0].artist[0].children:
                    if 'name' in response.metadata[0].artist[0].area[0].children:
                        return response.metadata[0].artist[0].area[0].name[0].text
            else:
                log.error("%s: %r: MusicBrainz artist xml result not in correct format - %s",
                          PLUGIN_NAME, artist_id, response)
        return None


register_track_metadata_processor(AlbumArtistArea().add_artist_area)
