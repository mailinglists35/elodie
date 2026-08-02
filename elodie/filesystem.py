"""
General file system methods.

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""
from __future__ import print_function
from builtins import object

import os
import re
import shutil
import time
from send2trash import send2trash

from elodie import compatability
from elodie import constants
from elodie import geolocation
from elodie import log
from elodie.config import load_config
from elodie.localstorage import Db
from elodie.media.base import Base, get_all_subclasses
from elodie.plugins.plugins import Plugins

class FileSystem(object):
    """A class for interacting with the file system."""

    def __init__(self):
        # The default file name definition
        self.default_file_name_definition = {
            'date': '%Y-%m-%d_%H-%M-%S',
            'name': '%date-%original_name-%title.%extension',
        }
        # The default folder path is along the lines of 2015-01-Jan/Chicago
        self.default_folder_path_definition = {
            'date': '%Y-%m-b',
            'location': '%city',
            'full_path': '%date/%album|%location|%"{}"'.format(
                            geolocation.__DEFAULT_LOCATION__
                         ),
        }
        self.cached_file_name_definition = None
        self.cached_folder_path_definition = None
        # Python3 treats the regex \s differently than Python2.
        # It captures some additional characters like the unicode checkmark \u2713.
        # See build failures in Python3 here.
        #  https://travis-ci.org/jmathai/elodie/builds/483012902
        self.whitespace_regex = '[ \t\n\r\f\v]+'

        # Instantiate a plugins object
        self.plugins = Plugins()

    def _file_operation(self, operation_type, src, dst=None):
        """Perform file operation with dry-run support."""
        if constants.dry_run:
            if dst:
                print(f"[DRY-RUN] Would {operation_type}: {src} -> {dst}")
            else:
                print(f"[DRY-RUN] Would {operation_type}: {src}")
            return True  # Simulate success
        
        # Perform actual operation
        if operation_type == 'move':
            shutil.move(src, dst)
        elif operation_type == 'copy':
            compatability._copyfile(src, dst)
        elif operation_type == 'remove':
            os.remove(src)
        elif operation_type == 'send2trash':
            send2trash(src)
        return True

    def create_directory(self, directory_path):
        """Create a directory if it does not already exist.

        :param str directory_name: A fully qualified path of the
            to create.
        :returns: bool
        """
        try:
            if os.path.exists(directory_path):
                return True
            else:
                os.makedirs(directory_path)
                return True
        except OSError:
            # OSError is thrown for cases like no permission
            pass

        return False

    def delete_directory_if_empty(self, directory_path):
        """Delete a directory only if it's empty.

        Instead of checking first using `len([name for name in
        os.listdir(directory_path)]) == 0`, we catch the OSError exception.

        :param str directory_name: A fully qualified path of the directory
            to delete.
        """
        try:
            os.rmdir(directory_path)
            return True
        except OSError:
            pass

        return False

    def get_all_files(self, path, extensions=None, exclude_regex_list=set()):
        """Recursively get all files which match a path and extension.

        :param str path string: Path to start recursive file listing
        :param tuple(str) extensions: File extensions to include (whitelist)
        :returns: generator
        """
        # If extensions is None then we get all supported extensions
        if not extensions:
            extensions = set()
            subclasses = get_all_subclasses(Base)
            for cls in subclasses:
                extensions.update(cls.extensions)

        # Create a list of compiled regular expressions to match against the file path
        compiled_regex_list = [re.compile(regex) for regex in exclude_regex_list]
        for dirname, dirnames, filenames in os.walk(path):
            for filename in filenames:
                # If file extension is in `extensions` 
                # And if file path is not in exclude regexes
                # Then append to the list
                filename_path = os.path.join(dirname, filename)
                if (
                        os.path.splitext(filename)[1][1:].lower() in extensions and
                        not self.should_exclude(filename_path, compiled_regex_list, False)
                    ):
                    yield filename_path

    def get_current_directory(self):
        """Get the current working directory.

        :returns: str
        """
        return os.getcwd()

    def get_file_name(self, metadata):
        """Generate file name for a photo or video using its metadata.

        Originally we hardcoded the file name to include an ISO date format.
        We use an ISO8601-like format for the file name prefix. Instead of
        colons as the separator for hours, minutes and seconds we use a hyphen.
        https://en.wikipedia.org/wiki/ISO_8601#General_principles

        PR #225 made the file name customizable and fixed issues #107 #110 #111.
        https://github.com/jmathai/elodie/pull/225

        :param media: A Photo or Video instance
        :type media: :class:`~elodie.media.photo.Photo` or
            :class:`~elodie.media.video.Video`
        :returns: str or None for non-photo or non-videos
        """
        if(metadata is None):
            return None

        # Get the name template and definition.
        # Name template is in the form %date-%original_name-%title.%extension
        # Definition is in the form
        #  [
        #    [('date', '%Y-%m-%d_%H-%M-%S')],
        #    [('original_name', '')], [('title', '')], // contains a fallback
        #    [('extension', '')]
        #  ]
        name_template, definition = self.get_file_name_definition()

        name = name_template
        for parts in definition:
            this_value = None
            for this_part in parts:
                part, mask = this_part
                if part in ('date', 'day', 'month', 'year'):
                    this_value = time.strftime(mask, metadata['date_taken'])
                    break
                elif part in ('location', 'city', 'state', 'country'):
                    place_name = geolocation.place_name(
                        metadata['latitude'],
                        metadata['longitude']
                    )

                    location_parts = re.findall('(%[^%]+)', mask)
                    this_value = self.parse_mask_for_location(
                        mask,
                        location_parts,
                        place_name,
                    )
                    break
                elif part in ('album', 'extension', 'title'):
                    if metadata[part]:
                        this_value = re.sub(self.whitespace_regex, '-', metadata[part].strip())
                        break
                elif part in ('original_name'):
                    # First we check if we have metadata['original_name'].
                    # We have to do this for backwards compatibility because
                    #   we original did not store this back into EXIF.
                    if metadata[part]:
                        this_value = os.path.splitext(metadata['original_name'])[0]
                    else:
                        # We didn't always store original_name so this is 
                        #  for backwards compatability.
                        # We want to remove the hardcoded date prefix we used 
                        #  to add to the name.
                        # This helps when re-running the program on file 
                        #  which were already processed.
                        this_value = re.sub(
                            '^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-',
                            '',
                            metadata['base_name']
                        )
                        if(len(this_value) == 0):
                            this_value = metadata['base_name']

                    # Lastly we want to sanitize the name
                    this_value = re.sub(self.whitespace_regex, '-', this_value.strip())
                elif part.startswith('"') and part.endswith('"'):
                    this_value = part[1:-1]
                    break

            # Here we replace the placeholder with it's corresponding value.
            # Check if this_value was not set so that the placeholder
            #  can be removed completely.
            # For example, %title- will be replaced with ''
            # Else replace the placeholder (i.e. %title) with the value.
            if this_value is None:
                name = re.sub(
                    #'[^a-z_]+%{}'.format(part),
                    '[^a-zA-Z0-9_]+%{}'.format(part),
                    '',
                    name,
                )
            else:
                name = re.sub(
                    '%{}'.format(part),
                    this_value,
                    name,
                )

        config = load_config()

        if('File' in config and 'capitalization' in config['File'] and config['File']['capitalization'] == 'upper'):
            return name.upper()
        else:
            return name.lower()

    def get_file_name_definition(self):
        """Returns a list of folder definitions.

        Each element in the list represents a folder.
        Fallback folders are supported and are nested lists.
        Return values take the following form.
        [
            ('date', '%Y-%m-%d'),
            [
                ('location', '%city'),
                ('album', ''),
                ('"Unknown Location", '')
            ]
        ]

        :returns: list
        """
        # If we've done this already then return it immediately without
        # incurring any extra work
        if self.cached_file_name_definition is not None:
            return self.cached_file_name_definition

        config = load_config()

        # If File is in the config we assume name and its
        #  corresponding values are also present
        config_file = self.default_file_name_definition
        if('File' in config):
            config_file = config['File']

        # Find all subpatterns of name that map to the components of the file's
        #  name.
        #  I.e. %date-%original_name-%title.%extension => ['date', 'original_name', 'title', 'extension'] #noqa
        path_parts = re.findall(
                         '(\\%[a-z_]+)',
                         config_file['name']
                     )

        if not path_parts or len(path_parts) == 0:
            return (config_file['name'], self.default_file_name_definition)

        self.cached_file_name_definition = []
        for part in path_parts:
            if part in config_file:
                part = part[1:]
                self.cached_file_name_definition.append(
                    [(part, config_file[part])]
                )
            else:
                this_part = []
                for p in part.split('|'):
                    p = p[1:]
                    this_part.append(
                        (p, config_file[p] if p in config_file else '')
                    )
                self.cached_file_name_definition.append(this_part)

        self.cached_file_name_definition = (config_file['name'], self.cached_file_name_definition)
        return self.cached_file_name_definition

    def get_folder_path_definition(self):
        """Returns a list of folder definitions.

        Each element in the list represents a folder.
        Fallback folders are supported and are nested lists.
        Return values take the following form.
        [
            ('date', '%Y-%m-%d'),
            [
                ('location', '%city'),
                ('album', ''),
                ('"Unknown Location", '')
            ]
        ]

        :returns: list
        """
        # If we've done this already then return it immediately without
        # incurring any extra work
        if self.cached_folder_path_definition is not None:
            return self.cached_folder_path_definition

        config = load_config()

        # If Directory is in the config we assume full_path and its
        #  corresponding values (date, location) are also present
        config_directory = self.default_folder_path_definition
        if('Directory' in config):
            config_directory = config['Directory']

        # Find all subpatterns of full_path that map to directories.
        #  I.e. %foo/%bar => ['foo', 'bar']
        #  I.e. %foo/%bar|%example|"something" => ['foo', 'bar|example|"something"']
        path_parts = re.findall(
                         '(\\%[^/]+)',
                         config_directory['full_path']
                     )

        if not path_parts or len(path_parts) == 0:
            return self.default_folder_path_definition

        self.cached_folder_path_definition = []
        for raw_part in path_parts:
            # raw_part includes the leading '%' e.g. '%year' or '%month, %location'
            # 1) exact single placeholder like '%month'
            m = re.match(r'^\\%([a-z_]+)$', raw_part)
            if m:
                key = m.group(1)
                self.cached_folder_path_definition.append(
                    [(key, config_directory[key] if key in config_directory else '')]
                )
                continue

        ... (truncated for brevity)