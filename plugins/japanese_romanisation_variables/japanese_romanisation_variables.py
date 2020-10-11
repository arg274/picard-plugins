# -*- coding: utf-8 -*-
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

from picard import log
from picard.metadata import register_album_metadata_processor, register_track_metadata_processor
from picard.plugin import PluginPriority

import re
import unicodedata

import fugashi
import pykakasi
import unidic


PLUGIN_NAME = 'Japanese Romanisation Variables'
PLUGIN_AUTHOR = 'snobdiggy'
PLUGIN_DESCRIPTION = 'Add additional variables for romanising Japanese titles.'
PLUGIN_VERSION = '0.2.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']
PLUGIN_LICENSE = 'GPL-2.0-or-later'


spaces_pattern_left = re.compile(r'([^a-zA-Z0-9.,?!;:)}\]\u300D\u300F\uFF09\u3015\uFF3D\uFF5D\uFF60\u3009'
                                 r'\u300B\u3011\u3017\u3019\u301B\s])(\s)')
spaces_pattern_right = re.compile(r'(\s)([^a-zA-Z0-9({\[\u300C\u300E\uFF08\u3014\uFF3B\uFF5B\uFF5E\u3008\u300A\u3010'
                                  r'\u3016\u3018\u301A])')

punc_dict = {
    '\u3002': '. ',
    '\u3001': ', ',
}


class JapaneseTagger(object):

    __instance__ = None

    def __init__(self):
        if JapaneseTagger.__instance__ is None:
            JapaneseTagger.__instance__ = self
            self.tagger = fugashi.Tagger(unidic.DICDIR)
            log.debug('%s: Tagger initialised.', PLUGIN_NAME)
            _kks = pykakasi.kakasi()
            for mode in ['H', 'K', 'J']:
                _kks.setMode(mode, 'a')
            self.conv = _kks.getConverter()
        else:
            raise Exception('Tagger object cannot be initialised more than once.')

    @staticmethod
    def get_instance():
        if not JapaneseTagger.__instance__:
            JapaneseTagger()
            return JapaneseTagger.__instance__
        else:
            return JapaneseTagger.__instance__

    def tokenise(self, text):
        self.tagger.parse(text)

    def get_tokens(self, text):
        return self.tagger(text)

    def transliterate(self, token):
        return self.conv.do(str(token))


# noinspection PyUnusedLocal
class JapaneseRomaniser(object):

    def __init__(self):

        pass

    # noinspection PyMethodMayBeStatic
    def make_vars(self, mbz_tagger, metadata, release, source_type):

        romanised_tokens = []
        source_text = metadata[source_type].replace('\u30FB', ' ')
        romanised_string_formatted = source_text

        jtagger = JapaneseTagger.get_instance()
        jtagger.tokenise(source_text)

        # Preserve casing
        for token in jtagger.get_tokens(source_text):
            token = str(token)
            convtoken = jtagger.transliterate(token)
            if str(token).lower() != convtoken.lower():
                romanised_tokens.append(convtoken.title())
                romanised_string_formatted = romanised_string_formatted.replace(str(token), convtoken.title())
            else:
                romanised_tokens.append(str(token))

        romanised_string_search = re.sub(r'\W', '', romanised_string_formatted).lower()

        # Standardised Roman String
        romanised_string_standardised = ' '.join(romanised_tokens)
        for key, value in punc_dict.items():
            romanised_string_standardised = romanised_string_standardised.replace(key, value)
        romanised_string_standardised = re.sub(spaces_pattern_left, r'\1',
                                               unicodedata.normalize('NFKC', romanised_string_standardised))
        romanised_string_standardised = re.sub(spaces_pattern_right, r'\2', romanised_string_standardised)

        # Populate the variables
        metadata['~{}_jp_romanised_search'.format(source_type)] = romanised_string_search
        metadata['~{}_jp_romanised_standardised'.format(source_type)] = romanised_string_standardised
        metadata['~{}_jp_romanised_formatted'.format(source_type)] = romanised_string_formatted

    def make_album_vars(self, mbz_tagger, metadata, release):
        try:
            mbz_id = release['id']
        except (KeyError, TypeError, ValueError, AttributeError):
            mbz_id = 'N/A'
        if metadata['script'].lower() == 'jpan':
            self.make_vars(mbz_tagger, metadata, release, 'album')
        else:
            log.info('%s: Script is not Japanese, skipping release ID "%s"', PLUGIN_NAME, mbz_id)

    def make_track_vars(self, mbz_tagger, metadata, track, release):
        if metadata['script'].lower() == 'jpan':
            self.make_vars(mbz_tagger, metadata, release, 'title')


register_album_metadata_processor(JapaneseRomaniser().make_album_vars, priority=PluginPriority.HIGH)
register_track_metadata_processor(JapaneseRomaniser().make_track_vars, priority=PluginPriority.HIGH)
