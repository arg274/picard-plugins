from picard import log
from picard.metadata import register_album_metadata_processor, register_track_metadata_processor
from picard.plugin import PluginPriority

import re

from .korean_romanizer import Romanizer


PLUGIN_NAME = 'Korean Romanisation Variables'
PLUGIN_AUTHOR = 'snobdiggy'
PLUGIN_DESCRIPTION = 'Add additional variables for romanising Korean titles.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']
PLUGIN_LICENSE = 'GPL-2.0-or-later'


spaces_pattern_left = re.compile(r'([^a-zA-Z0-9.,?!;:)}\]\u300D\u300F\uFF09\u3015\uFF3D\uFF5D\uFF60\u3009'
                                 r'\u300B\u3011\u3017\u3019\u301B\s])(\s)')
spaces_pattern_right = re.compile(r'(\s)([^a-zA-Z0-9({\[\u300C\u300E\uFF08\u3014\uFF3B\uFF5B\uFF5E\u3008\u300A\u3010'
                                  r'\u3016\u3018\u301A])')


# noinspection PyUnusedLocal
class KoreanRomaniser(object):

    def __init__(self):

        pass

    # noinspection PyMethodMayBeStatic
    def make_vars(self, mbz_tagger, metadata, release, source_type):

        romanised_tokens = []

        source_text = metadata[source_type]
        romanised_string_formatted = source_text

        __re_pattern = re.compile(r'[\w]+|[\W]')

        romanised_prim_tokens = __re_pattern.findall(source_text)
        romanised_prim_tokens = [token for token in romanised_prim_tokens if token != ' ']

        # Preserve casing
        for token in romanised_prim_tokens:
            convtoken = Romanizer.romanize(token)
            if token.lower() != convtoken.lower():
                romanised_tokens.append(convtoken.title())
                romanised_string_formatted = romanised_string_formatted.replace(token, convtoken.title())
            else:
                romanised_tokens.append(token)

        romanised_string_search = re.sub(r'\W', '', romanised_string_formatted).lower()

        # Standardised Roman String
        romanised_string_standardised = ' '.join(romanised_tokens)
        romanised_string_standardised = re.sub(spaces_pattern_left, r'\1', romanised_string_standardised)
        romanised_string_standardised = re.sub(spaces_pattern_right, r'\2', romanised_string_standardised)

        log.debug('%s: %s | %s | %s', PLUGIN_NAME, romanised_string_formatted, romanised_string_standardised,
                  romanised_string_search)

        # Populate the variables
        metadata['~{}_kr_romanised_search'.format(source_type)] = romanised_string_search
        metadata['~{}_kr_romanised_standardised'.format(source_type)] = romanised_string_standardised
        metadata['~{}_kr_romanised_formatted'.format(source_type)] = romanised_string_formatted

    def make_album_vars(self, mbz_tagger, metadata, release):
        try:
            mbz_id = release['id']
        except (KeyError, TypeError, ValueError, AttributeError):
            mbz_id = 'N/A'
        if metadata['script'].lower() == 'kore' or metadata['script'].lower() == 'hang':
            self.make_vars(mbz_tagger, metadata, release, 'album')
        else:
            log.info('%s: Script is not Korean, skipping release ID "%s"', PLUGIN_NAME, mbz_id)

    def make_track_vars(self, mbz_tagger, metadata, track, release):
        if metadata['script'].lower() == 'kore' or metadata['script'].lower() == 'hang':
            self.make_vars(mbz_tagger, metadata, release, 'title')


register_album_metadata_processor(KoreanRomaniser().make_album_vars, priority=PluginPriority.HIGH)
register_track_metadata_processor(KoreanRomaniser().make_track_vars, priority=PluginPriority.HIGH)
