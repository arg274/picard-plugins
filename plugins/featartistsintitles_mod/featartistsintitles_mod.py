# -*- coding: utf-8 -*-

from picard.metadata import register_album_metadata_processor, register_track_metadata_processor
from picard.plugin import PluginPriority
import re


PLUGIN_NAME = 'Feat. Artists in Titles (Modified)'
PLUGIN_AUTHOR = 'Lukas Lalinsky, Michael Wiencek, Bryan Toth, JeromyNix (NobahdiAtoll), snobdiggy'
PLUGIN_DESCRIPTION = 'Move "feat." from artist names to track titles. Removes "feat." from album artists.' \
                     'Match is case insensitive.'
PLUGIN_VERSION = "0.1.1"
PLUGIN_API_VERSIONS = ["0.9.0", "0.10", "0.15", "0.16", "2.0"]

_feat_re = re.compile(r"([\s\S]+) feat\.([\s\S]+)", re.IGNORECASE)


def remove_album_featartists(tagger, metadata, release):
    for field in ['albumartist', 'albumartistsort']:
        match = _feat_re.match(metadata[field])
        if match:
            metadata[field] = match.group(1)


def move_track_featartists(tagger, metadata, track, release):
    for field in ['artist', 'artistsort']:
        if metadata[field]:
            match = _feat_re.match(metadata[field])
            if match:
                metadata[field] = match.group(1)
                if field == 'artist':
                    metadata['title'] += " (feat.%s)" % match.group(2)


register_album_metadata_processor(remove_album_featartists, priority=PluginPriority.LOW)
register_track_metadata_processor(move_track_featartists, priority=PluginPriority.LOW)
