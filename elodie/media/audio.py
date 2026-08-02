"""
The audio module contains classes specifically for dealing with audio files.
The :class:`Audio` class inherits from the :class:`~elodie.media.video.Video`
class.

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""
from __future__ import absolute_import

from .video import Video


class Audio(Video):

    """An audio object.

    :param str source: The fully qualified path to the audio file.
    """

    __name__ = 'Audio'

    #: Valid extensions for audio files.
    extensions = ('m4a',)

    def __init__(self, source=None, allow_metadata_writes=False):
        super(Audio, self).__init__(source, allow_metadata_writes=allow_metadata_writes)
