import re
from functools import partial

from picard.util import LockableObject
from picard.webservice import ratecontrol
from picard.metadata import register_track_metadata_processor
from picard import log


PLUGIN_NAME = 'VGMdb Variables'
PLUGIN_AUTHOR = 'snobdiggy'
PLUGIN_DESCRIPTION = 'Add additional variables fot VGMdb data. Only adds variables for products associated ' \
                     'with a release for the moment being.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']


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
        self.albumpage_cache = {}
        self.albumpage_queue = self.VGMdbMetadataQueue()
        ratecontrol.set_minimum_delay((self.vgmdb_host, self.vgmdb_port), self.vgmdb_delay)

    # noinspection PyMethodMayBeStatic,PyProtectedMember
    def album_add_request(self, tagger):
        tagger._requests += 1

    # noinspection PyMethodMayBeStatic,PyProtectedMember
    def album_remove_request(self, tagger):
        tagger._requests -= 1
        tagger._finalize_loading(None)

    def get_vgmdb_id(self, release_dict):

        if 'relations' in release_dict:
            relations = release_dict['relations']

            for relation in relations:
                if 'type' in relation and relation['type'] == 'vgmdb':
                    url = relation['url']['resource']
                    vgmdb_id = re.search(self.vgmdb_url_pattern, url).group(1)
                    return vgmdb_id

        return None

    # noinspection PyMethodMayBeStatic
    def get_vgmdb_products(self, response):

        try:
            product_list_en = []
            product_list_jp = []
            products = response['products']
            for product in products:
                product_list_en.append(product['names']['en'])
                if 'ja' in product['names']:
                    product_list_jp.append(product['names']['ja'])

            return product_list_en, product_list_jp

        except (KeyError, TypeError, ValueError, AttributeError):
            log.warning('%s: Key error', PLUGIN_NAME)
            return None, None

    def vgmdb_process(self, vgmdb_id, response, reply, error):

        if error:
            log.error('%s: %s', PLUGIN_NAME, error)
            tuples = self.albumpage_queue.remove(vgmdb_id)
            for track_obj, tagger in tuples:
                self.album_remove_request(tagger)
            return

        en_products, jp_products = self.get_vgmdb_products(response)
        self.albumpage_cache[vgmdb_id] = (en_products, jp_products)

        tuples = self.albumpage_queue.remove(vgmdb_id)

        for track_obj, tagger in tuples:

            track_metadata = track_obj.metadata

            if en_products:
                track_metadata['~vgmdb_products_en'] = en_products
            else:
                log.warning('%s: English product title not found', PLUGIN_NAME)
            if jp_products:
                track_metadata['~vgmdb_products_jp'] = jp_products
            else:
                log.debug('%s: Japanese product title not found', PLUGIN_NAME)

            self.album_remove_request(tagger)

    def make_vgmdb_request(self, tagger, track_obj, vgmdb_id):

        self.album_add_request(tagger)

        if self.albumpage_queue.append(vgmdb_id, (track_obj, tagger)):

            path = '/album/{}'.format(vgmdb_id)
            params = {'format': 'json'}

            log.debug('%s: Querying "https://%s%s&format=json"', PLUGIN_NAME, self.vgmdb_host, path)

            return tagger.tagger.webservice.get(self.vgmdb_host, self.vgmdb_port, path,
                                                partial(self.vgmdb_process, vgmdb_id),
                                                queryargs=params, parse_response_type='json')

    def apply_vgmdb_metadata(self, tagger, metadata, track_dict, release_dict):

        vgmdb_id = self.get_vgmdb_id(release_dict)

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
                # noinspection PyProtectedMember
                self.make_vgmdb_request(tagger, tagger._new_tracks[-1], vgmdb_id)


register_track_metadata_processor(VGMdbMetadataProcessor().apply_vgmdb_metadata)
