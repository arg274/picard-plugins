import re
import unicodedata
from functools import partial

from picard.util import LockableObject
from picard.webservice import ratecontrol
from picard.metadata import register_track_metadata_processor
from picard import log


PLUGIN_NAME = 'VGMdb Variables'
PLUGIN_AUTHOR = 'snobdiggy'
PLUGIN_DESCRIPTION = 'Add additional variables fot VGMdb data. Only adds variables for products associated ' \
                     'with a release for the moment being.'
PLUGIN_VERSION = '0.2.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']


# noinspection PyUnusedLocal
class VGMdbMetadataProcessor(object):

    class VGMdbMetadataQueue(LockableObject):

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

    vgmdb_host = 'vgmdb.info'
    vgmdb_port = 443
    vgmdb_delay = 60 * 1000 / 100

    vgmdb_url_pattern = re.compile(r'https?://vgmdb\.net/.*/(\d+).*')

    def __init__(self):

        self.search_route = False
        self.search_route_iter_idx = 0

        self.albumpage_cache = {}
        self.albumpage_queue = self.VGMdbMetadataQueue()
        self.searchpage_cache = {}
        self.searchpage_queue = self.VGMdbMetadataQueue()

        ratecontrol.set_minimum_delay((self.vgmdb_host, self.vgmdb_port), self.vgmdb_delay)

    # noinspection PyMethodMayBeStatic,PyProtectedMember
    def album_add_request(self, tagger):
        tagger._requests += 1

    # noinspection PyMethodMayBeStatic,PyProtectedMember
    def album_remove_request(self, tagger):
        tagger._requests -= 1
        tagger._finalize_loading(None)

    def search_mode_isenabled(self):
        return self.search_route

    def search_mode_enable(self):
        self.search_route = True

    def search_mode_increment(self):
        self.search_route_iter_idx += 1

    def search_mode_reset(self):
        self.search_route = False
        self.search_route_iter_idx = 0

    def check_album_request_cache(self, tagger, metadata, release_dict, vgmdb_id):

        if vgmdb_id is None:
            log.debug('%s: VGMdb ID not found for "%s"', PLUGIN_NAME, metadata['title'])
            return

        else:
            log.debug('%s: VGMdb ID is %s', PLUGIN_NAME, vgmdb_id)
            if vgmdb_id in self.albumpage_cache:
                en_products, jp_products = self.albumpage_cache[vgmdb_id]
                if en_products:
                    metadata['~vgmdb_products_en'] = en_products
                if jp_products:
                    metadata['~vgmdb_products_jp'] = jp_products
            else:
                if self.search_route is False:
                    # noinspection PyProtectedMember
                    self.make_vgmdb_request(tagger, tagger._new_tracks[-1], release_dict, vgmdb_id)
                else:
                    try:
                        # noinspection PyProtectedMember
                        self.make_vgmdb_request(tagger, tagger._new_tracks[self.search_route_iter_idx],
                                                release_dict, vgmdb_id)
                    except IndexError:
                        self.search_mode_reset()
                        # noinspection PyProtectedMember
                        self.make_vgmdb_request(tagger, tagger._new_tracks[self.search_route_iter_idx],
                                                release_dict, vgmdb_id)
                    finally:
                        self.search_mode_increment()

    def vgmdb_branching_controller(self, tagger, metadata, track_dict, release_dict):

        release_id = release_dict['id']
        vgmdb_id = None

        # Check VGMdb entry in cache
        if release_id in self.searchpage_cache:
            self.check_album_request_cache(tagger, metadata, release_dict, self.searchpage_cache[release_id])

        # Try to find VGMdb entry from MBZ data
        if 'relations' in release_dict:
            relations = release_dict['relations']

            for relation in relations:
                if 'type' in relation and relation['type'] == 'vgmdb':
                    url = relation['url']['resource']
                    vgmdb_id = re.search(self.vgmdb_url_pattern, url).group(1)
                    self.searchpage_cache[release_id] = vgmdb_id
                    self.check_album_request_cache(tagger, metadata, release_dict, vgmdb_id)
                    break

        # Try to find VGMdb entry using search
        if vgmdb_id is None:
            self.search_mode_enable()
            # noinspection PyProtectedMember
            self.make_vgmdb_search_request(tagger, metadata, release_dict)

    # noinspection PyMethodMayBeStatic
    def get_vgmdb_products(self, release_dict, response, strict_mode):

        def sanitise(string):
            pattern = re.compile(r'\W')
            return unicodedata.normalize('NFKC', re.sub(pattern, '', string))

        def pack_products(_response):

            product_list_en = []
            product_list_jp = []

            try:
                if 'products' in response:
                    products = response['products']
                    for product in products:
                        product_list_en.append(product['names']['en'])
                        if 'ja' in product['names']:
                            product_list_jp.append(product['names']['ja'])

                return product_list_en, product_list_jp

            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning('%s: Key error', PLUGIN_NAME)
                return None, None

        if not strict_mode:
            return pack_products(response)

        if 'artist-credit' not in release_dict:
            log.warning('%s: No artist credit', PLUGIN_NAME)
            return None, None

        source_artists = []
        vgmdb_artists = []

        for artist in release_dict['artist-credit']:
            if 'artist' in artist:
                source_artists.append(artist['artist']['name'].lower())

        for personnel_type in ['performers', 'composers', 'organizations']:
            if personnel_type in response:
                for personnel in response[personnel_type]:
                    for name in personnel['names']:
                        vgmdb_artists.append(personnel['names'][name].lower())

        if 'Various Artists' in source_artists:

            source_title = sanitise(release_dict['title'])
            vgmdb_titles = [sanitise(title.split(' / ')[0]) for title in response['names']]

            for vgmdb_title in vgmdb_titles:
                if vgmdb_title == source_title:
                    return pack_products(response)

            return None, None

        else:
            for vgmdb_artist in vgmdb_artists:
                for source_artist in source_artists:
                    if vgmdb_artist == source_artist:
                        return pack_products(response)

        return None, None

    # noinspection PyMethodMayBeStatic
    def get_vgmdb_id_from_search(self, release_dict, response):

        source_title = release_dict['title'].lower()

        try:
            albums = response['results']['albums']

            if albums:
                # VGMdb search seems to have no weight on similarity; attempt to get an exact match if lucky enough
                for album in albums:
                    for title in album['titles']:
                        # Their data separation is really mediocre; this might have unintended
                        # results if the album itself has a slash
                        title = title.split(' / ', 1)[0]
                        if title.lower() == source_title:
                            vgmdb_id = re.sub(r'album/', '', album['link'])
                            vgmdb_id = vgmdb_id if vgmdb_id != '' else None
                            return vgmdb_id
                # Just return the first album if no exact match is found, will get filtered later anyway
                vgmdb_id = re.sub(r'album/', '', albums[0]['link'])
                vgmdb_id = vgmdb_id if vgmdb_id != '' else None
                return vgmdb_id

            return None

        except (KeyError, TypeError, ValueError, AttributeError):
            log.warning('%s: Key error', PLUGIN_NAME)
            return None

    def vgmdb_process(self, release_dict, vgmdb_id, response, reply, error):

        if error:
            log.error('%s: %s', PLUGIN_NAME, error)
            tuples = self.albumpage_queue.remove(vgmdb_id)
            for track_obj, tagger in tuples:
                self.album_remove_request(tagger)
            return

        en_products, jp_products = self.get_vgmdb_products(release_dict, response, self.search_mode_isenabled())
        self.albumpage_cache[vgmdb_id] = (en_products, jp_products)

        tuples = self.albumpage_queue.remove(vgmdb_id)
        self.search_mode_reset()

        for track_obj, tagger in tuples:

            track_metadata = track_obj.metadata

            if en_products:
                track_metadata['~vgmdb_products_en'] = en_products
            else:
                log.debug('%s: English product title not found', PLUGIN_NAME)
            if jp_products:
                track_metadata['~vgmdb_products_jp'] = jp_products
            else:
                log.debug('%s: Japanese product title not found', PLUGIN_NAME)

            for file in track_obj.iterfiles(True):

                file_metadata = file.metadata

                if en_products:
                    file_metadata['~vgmdb_products_en'] = en_products
                if jp_products:
                    file_metadata['~vgmdb_products_jp'] = jp_products

            self.album_remove_request(tagger)

    def make_vgmdb_request(self, tagger, track_obj, release_dict, vgmdb_id):

        self.album_add_request(tagger)

        if self.albumpage_queue.append(vgmdb_id, (track_obj, tagger)):

            path = '/album/{}'.format(vgmdb_id)
            params = {'format': 'json'}

            log.debug('%s: Querying "https://%s%s&format=json"', PLUGIN_NAME, self.vgmdb_host, path)

            return tagger.tagger.webservice.get(self.vgmdb_host, self.vgmdb_port, path,
                                                partial(self.vgmdb_process, release_dict, vgmdb_id),
                                                queryargs=params, parse_response_type='json')

    def vgmdb_process_search(self, tagger, metadata, release_dict, response, reply, error):

        mbz_id = release_dict['id']

        if error:
            log.error('%s: %s', PLUGIN_NAME, error)
            tuples = self.searchpage_queue.remove(mbz_id)
            for tagger in tuples:
                self.album_remove_request(tagger)
            return

        vgmdb_id = self.get_vgmdb_id_from_search(release_dict, response)
        self.searchpage_cache[mbz_id] = vgmdb_id

        tuples = self.searchpage_queue.remove(mbz_id)

        for tagger in tuples:
            self.check_album_request_cache(tagger, metadata, release_dict, vgmdb_id)
            self.album_remove_request(tagger)

    def make_vgmdb_search_request(self, tagger, metadata, release_dict):

        mbz_id = release_dict['id']
        album_title = release_dict['title']

        self.album_add_request(tagger)

        if self.searchpage_queue.append(mbz_id, tagger):

            path = '/search/albums/{}'.format(album_title)
            params = {'format': 'json'}

            log.debug('%s: Querying "https://%s%s&format=json"', PLUGIN_NAME, self.vgmdb_host, path)

            return tagger.tagger.webservice.get(self.vgmdb_host, self.vgmdb_port, path,
                                                partial(self.vgmdb_process_search, tagger, metadata, release_dict),
                                                queryargs=params, parse_response_type='json',
                                                priority=True, important=True)


register_track_metadata_processor(VGMdbMetadataProcessor().vgmdb_branching_controller)
