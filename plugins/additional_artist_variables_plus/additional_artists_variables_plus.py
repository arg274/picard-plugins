# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Bob Swift (rdswift)
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


import re

from picard import log
from picard.metadata import (register_album_metadata_processor,
                             register_track_metadata_processor)
from picard.plugin import PluginPriority


PLUGIN_NAME = 'Additional Artists Variables Plus'
PLUGIN_AUTHOR = 'Bob Swift (rdswift), snobdiggy'
PLUGIN_DESCRIPTION = '''This plugin provides specialized album and track variables for use in naming scripts. It is 
based on the "Additional Artists Variables" plugin, but expands the functionality to also allow swapping of sort 
artists.'''
PLUGIN_VERSION = '0.2'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']
PLUGIN_LICENSE = 'GPL-2.0-or-later'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-2.0.html'


def process_feat_string(string):

    _feat_re = re.compile(r"([\s\S]+) feat\.([\s\S]+)", re.IGNORECASE)

    match = _feat_re.match(string)
    if match:
        return match.group(1), '(feat.{})'.format(match.group(2))

    return string, ''


def process_artists(album_id, source_metadata, destination_metadata, source_type):
    # Test for valid metadata node.
    # The 'artist-credit' key should always be there.
    # This check is to avoid a runtime error if it doesn't exist for some reason.
    if 'artist-credit' in source_metadata:
        # Initialize variables to default values
        sort_pri_artist = ''
        std_artist = ''
        cred_artist = ''
        sort_artist = ''
        sort_artist_swapped = ''
        additional_std_artist = ''
        additional_cred_artist = ''
        std_artist_list = []
        cred_artist_list = []
        sort_artist_list = []
        sort_artist_list_swapped = []
        artist_count = 0
        artist_ids = []

        for artist_credit in source_metadata['artist-credit']:
            # Initialize temporary variables for each loop.
            temp_std_name = ''
            temp_cred_name = ''
            temp_sort_name = ''
            temp_sort_name_swapped = ''
            temp_phrase = ''
            temp_id = ''
            # Check if there is a 'joinphrase' specified.
            if 'joinphrase' in artist_credit:
                temp_phrase = artist_credit['joinphrase']
            else:
                metadata_error(album_id, 'artist-credit.joinphrase', source_type)
            # Check if there is a 'name' specified.
            if 'name' in artist_credit:
                temp_cred_name = artist_credit['name']
            else:
                metadata_error(album_id, 'artist-credit.name', source_type)
            # Check if there is an 'artist' specified.
            if 'artist' in artist_credit:
                if 'id' in artist_credit['artist']:
                    temp_id = artist_credit['artist']['id']
                else:
                    metadata_error(album_id, 'artist-credit.artist.id', source_type)
                if 'name' in artist_credit['artist']:
                    temp_std_name = artist_credit['artist']['name']
                else:
                    metadata_error(album_id, 'artist-credit.artist.name', source_type)
                if 'sort-name' in artist_credit['artist']:
                    temp_sort_name = artist_credit['artist']['sort-name']
                    temp_sort_name_swapped = swap_sort_artist(temp_sort_name)
                else:
                    metadata_error(album_id, 'artist-credit.artist.sort-name', source_type)
            else:
                # No 'artist' specified.  Log as an error.
                metadata_error(album_id, 'artist-credit.artist', source_type)
            std_artist += temp_std_name + temp_phrase
            cred_artist += temp_cred_name + temp_phrase
            sort_artist += temp_sort_name + temp_phrase
            sort_artist_swapped += temp_sort_name_swapped + temp_phrase
            if temp_std_name:
                std_artist_list.append(temp_std_name,)
            if temp_cred_name:
                cred_artist_list.append(temp_cred_name,)
            if temp_sort_name:
                sort_artist_list.append(temp_sort_name,)
            if temp_sort_name_swapped:
                sort_artist_list_swapped.append(temp_sort_name_swapped,)
            if temp_id:
                artist_ids.append(temp_id,)
            if artist_count < 1:
                if temp_id:
                    destination_metadata['~artists_{0}_primary_id'.format(source_type,)] = temp_id
                destination_metadata['~artists_{0}_primary_std'.format(source_type,)] = temp_std_name
                destination_metadata['~artists_{0}_primary_cred'.format(source_type,)] = temp_cred_name
                destination_metadata['~artists_{0}_primary_sort'.format(source_type,)] = temp_sort_name
                sort_pri_artist += temp_sort_name + temp_phrase
            else:
                sort_pri_artist += temp_std_name + temp_phrase
                additional_std_artist += temp_std_name + temp_phrase
                additional_cred_artist += temp_cred_name + temp_phrase
            artist_count += 1

        additional_std_artist_list = std_artist_list[1:]
        additional_cred_artist_list = cred_artist_list[1:]
        additional_sort_artist_list = sort_artist_list[1:]
        additional_artist_ids = artist_ids[1:]
        if additional_artist_ids:
            destination_metadata['~artists_{0}_additional_id'.format(source_type, )] = additional_artist_ids
        if additional_std_artist:
            destination_metadata['~artists_{0}_additional_std'.format(source_type, )] = additional_std_artist
        if additional_cred_artist:
            destination_metadata['~artists_{0}_additional_cred'.format(source_type, )] = additional_cred_artist
        if additional_std_artist_list:
            destination_metadata['~artists_{0}_additional_std_multi'.format(source_type, )] = additional_std_artist_list
        if additional_cred_artist_list:
            destination_metadata[
                '~artists_{0}_additional_cred_multi'.format(source_type, )] = additional_cred_artist_list
        if additional_sort_artist_list:
            destination_metadata[
                '~artists_{0}_additional_sort_multi'.format(source_type, )] = additional_sort_artist_list
        if std_artist:
            destination_metadata['~artists_{0}_all_std'.format(source_type, )] = std_artist
        if cred_artist:
            destination_metadata['~artists_{0}_all_cred'.format(source_type, )] = cred_artist
        if sort_artist:
            destination_metadata['~artists_{0}_all_sort'.format(source_type, )] = sort_artist
        if sort_artist_swapped:
            destination_metadata['~artists_{0}_all_sort_swapped'.format(source_type, )] = sort_artist_swapped
            sort_nofeat_artist_swapped, sort_feat_artist_swapped = process_feat_string(sort_artist_swapped)
            destination_metadata['~artists_{0}_nofeat_sort_swapped'.format(source_type, )] = sort_nofeat_artist_swapped
            destination_metadata['~artists_{0}_feat_sort_swapped'.format(source_type, )] = sort_feat_artist_swapped
        if std_artist_list:
            destination_metadata['~artists_{0}_all_std_multi'.format(source_type, )] = std_artist_list
        if cred_artist_list:
            destination_metadata['~artists_{0}_all_cred_multi'.format(source_type, )] = cred_artist_list
        if sort_artist_list:
            destination_metadata['~artists_{0}_all_sort_multi'.format(source_type, )] = sort_artist_list
        if sort_artist_list_swapped:
            destination_metadata['~artists_{0}_all_sort_swapped_multi'.format(source_type, )] = sort_artist_list_swapped
        if sort_pri_artist:
            destination_metadata['~artists_{0}_all_sort_primary'.format(source_type, )] = sort_pri_artist
        if artist_count:
            destination_metadata['~artists_{0}_all_count'.format(source_type, )] = artist_count
    else:
        # No valid metadata found.  Log as error.
        metadata_error(album_id, 'artist-credit', source_type)


def swap_sort_artist(sort_artist):
    if sort_artist is not None and ', ' in sort_artist:
        names = sort_artist.split(', ', 1)
        return '{} {}'.format(names[1], names[0])
    return sort_artist


def make_album_vars(album, album_metadata, release_metadata):
    album_id = release_metadata['id'] if release_metadata else 'No Album ID'
    process_artists(album_id, release_metadata, album_metadata, 'album')


def make_track_vars(album, album_metadata, track_metadata, release_metadata):
    album_id = release_metadata['id'] if release_metadata else 'No Album ID'
    process_artists(album_id, track_metadata, album_metadata, 'track')


def metadata_error(album_id, metadata_element, metadata_group):
    log.error("{0}: {1!r}: Missing '{2}' in {3} metadata.".format(
            PLUGIN_NAME, album_id, metadata_element, metadata_group,))


# Register the plugin to run at a LOW priority so that other plugins that
# modify the artist information can complete their processing and this plugin
# is working with the latest updated data.
register_album_metadata_processor(make_album_vars, priority=PluginPriority.LOW)
register_track_metadata_processor(make_track_vars, priority=PluginPriority.LOW)
