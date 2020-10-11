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

from googletrans import Translator


PLUGIN_NAME = 'Google Translate Romanisation Variables'
PLUGIN_AUTHOR = 'snobdiggy'
PLUGIN_DESCRIPTION = 'Add additional variables for romanising titles using the Google AJAX API.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']
PLUGIN_LICENSE = 'GPL-2.0-or-later'


banned_scripts = ['latn', 'jpan', 'kore', 'hang']


class GoogleTagger(object):

    __instance__ = None

    def __init__(self):
        if GoogleTagger.__instance__ is None:
            GoogleTagger.__instance__ = self
            self.tagger = Translator()
        else:
            raise Exception('Tagger object cannot be initialised more than once.')

    @staticmethod
    def get_instance():
        if not GoogleTagger.__instance__:
            GoogleTagger()
            return GoogleTagger.__instance__
        else:
            return GoogleTagger.__instance__

    def transliterate(self, text):
        try:
            return self.tagger.translate(text).extra_data['translation'][-1][-1]
        except (KeyError, ValueError, AttributeError, TypeError):
            log.error('%s: Error in parsing Translated result', PLUGIN_NAME)


# noinspection PyUnusedLocal
class GoogleRomaniser(object):

    def __init__(self):

        pass

    # noinspection PyMethodMayBeStatic
    def make_vars(self, mbz_tagger, metadata, release, source_type):

        source_text = metadata[source_type]

        gtagger = GoogleTagger.get_instance()
        romanised_string = gtagger.transliterate(source_text)

        if romanised_string:
            romanised_string_search = re.sub(r'\W', '', romanised_string).lower()

            # Populate the variables
            metadata['~{}_google_romanised_search'.format(source_type)] = romanised_string_search
            metadata['~{}_google_romanised'.format(source_type)] = romanised_string
        else:
            log.error('%s: Romanisation failed', PLUGIN_NAME)

    def make_album_vars(self, mbz_tagger, metadata, release):

        try:
            mbz_id = release['id']
        except (KeyError, TypeError, ValueError, AttributeError):
            mbz_id = 'N/A'
        if metadata['script'].lower() not in banned_scripts:
            self.make_vars(mbz_tagger, metadata, release, 'album')
        else:
            log.info('%s: Script is not whitelisted, skipping release ID "%s"', PLUGIN_NAME, mbz_id)

    def make_track_vars(self, mbz_tagger, metadata, track, release):
        if metadata['script'].lower() not in banned_scripts:
            self.make_vars(mbz_tagger, metadata, release, 'title')


register_album_metadata_processor(GoogleRomaniser().make_album_vars, priority=PluginPriority.HIGH)
register_track_metadata_processor(GoogleRomaniser().make_track_vars, priority=PluginPriority.HIGH)
