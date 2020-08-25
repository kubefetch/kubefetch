# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

#############################################
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import fnmatch
import os
import re
import itertools

from ansible import constants as C
from ansible.errors import AnsibleError, AnsibleOptionsError, AnsibleParserError
from ansible.inventory.data import InventoryData
from ansible.module_utils.six import string_types
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.parsing.utils.addresses import parse_address
from ansible.plugins.loader import PluginLoader
from ansible.utils.path import unfrackpath

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

IGNORED_ALWAYS = [b"^\.", b"^host_vars$", b"^group_vars$", b"^vars_plugins$"]
IGNORED_PATTERNS = [to_bytes(x) for x in C.INVENTORY_IGNORE_PATTERNS]
IGNORED_EXTS = [b'%s$' % to_bytes(re.escape(x)) for x in C.INVENTORY_IGNORE_EXTS]

IGNORED = re.compile(b'|'.join(IGNORED_ALWAYS + IGNORED_PATTERNS + IGNORED_EXTS))


def order_patterns(patterns):
    ''' takes a list of patterns and reorders them by modifier to apply them consistently '''

    # FIXME: this goes away if we apply patterns incrementally or by groups
    pattern_regular = []
    pattern_intersection = []
    pattern_exclude = []
    for p in patterns:
        if p.startswith("!"):
            pattern_exclude.append(p)
        elif p.startswith("&"):
            pattern_intersection.append(p)
        elif p:
            pattern_regular.append(p)

    # if no regular pattern was given, hence only exclude and/or intersection
    # make that magically work
    if pattern_regular == []:
        pattern_regular = ['all']

    # when applying the host selectors, run those without the "&" or "!"
    # first, then the &s, then the !s.
    return pattern_regular + pattern_intersection + pattern_exclude


def split_host_pattern(pattern):
    """
    Takes a string containing host patterns separated by commas (or a list
    thereof) and returns a list of single patterns (which may not contain
    commas). Whitespace is ignored.

    Also accepts ':' as a separator for backwards compatibility, but it is
    not recommended due to the conflict with IPv6 addresses and host ranges.

    Example: 'a,b[1], c[2:3] , d' -> ['a', 'b[1]', 'c[2:3]', 'd']
    """

    if isinstance(pattern, list):
        return list(itertools.chain(*map(split_host_pattern, pattern)))
    elif not isinstance(pattern, string_types):
        pattern = to_native(pattern)

    # If it's got commas in it, we'll treat it as a straightforward
    # comma-separated list of patterns.
    if ',' in pattern:
        patterns = re.split('\s*,\s*', pattern)

    # If it doesn't, it could still be a single pattern. This accounts for
    # non-separator uses of colons: IPv6 addresses and [x:y] host ranges.
    else:
        try:
            (base, port) = parse_address(pattern, allow_ranges=True)
            patterns = [pattern]
        except Exception:
            # The only other case we accept is a ':'-separated list of patterns.
            # This mishandles IPv6 addresses, and is retained only for backwards
            # compatibility.
            patterns = re.findall(
                r'''(?:             # We want to match something comprising:
                        [^\s:\[\]]  # (anything other than whitespace or ':[]'
                        |           # ...or...
                        \[[^\]]*\]  # a single complete bracketed expression)
                    )+              # occurring once or more
                ''', pattern, re.X
            )

    return [p.strip() for p in patterns]


class InventoryManager(object):
    ''' Creates and manages inventory '''

    def __init__(self, loader, sources=None):

        # base objects
        self._loader = loader
        self._inventory = InventoryData()

        # a list of host(names) to contain current inquiries to
        self._restriction = None
        self._subset = None

        # caches
        self._hosts_patterns_cache = {}  # resolved full patterns
        self._pattern_cache = {}  # resolved individual patterns
        self._inventory_plugins = []  # for generating inventory

        # the inventory dirs, files, script paths or lists of hosts
        if sources is None:
            self._sources = []
        elif isinstance(sources, string_types):
            self._sources = [sources]
        else:
            self._sources = sources

        # get to work!
        self.parse_sources()

    @property
    def localhost(self):
        return self._inventory.localhost

    @property
    def groups(self):
        return self._inventory.groups

    @property
    def hosts(self):
        return self._inventory.hosts

    def get_vars(self, *args, **kwargs):
        return self._inventory.get_vars(args, kwargs)

    def add_host(self, host, group=None, port=None):
        return self._inventory.add_host(host, group, port)

    def add_group(self, group):
        return self._inventory.add_group(group)

    def get_groups_dict(self):
        return self._inventory.get_groups_dict()

    def reconcile_inventory(self):
        self.clear_caches()
        return self._inventory.reconcile_inventory()

    def get_host(self, hostname):
        return self._inventory.get_host(hostname)

    def _setup_inventory_plugins(self):
        ''' sets up loaded inventory plugins for usage '''

        inventory_loader = PluginLoader('InventoryModule', 'ansible.plugins.inventory', C.DEFAULT_INVENTORY_PLUGIN_PATH, 'inventory_plugins')
        display.vvvv('setting up inventory plugins')

        for name in C.INVENTORY_ENABLED:
            plugin = inventory_loader.get(name)
            if plugin:
                self._inventory_plugins.append(plugin)
            else:
                display.warning('Failed to load inventory plugin, skipping %s' % name)

        if not self._inventory_plugins:
            raise AnsibleError("No inventory plugins available to generate inventory, make sure you have at least one whitelisted.")

    def parse_sources(self, cache=False):
        ''' iterate over inventory sources and parse each one to populate it'''

        self._setup_inventory_plugins()

        parsed = False
        # allow for multiple inventory parsing
        for source in self._sources:

            if source:
                if ',' not in source:
                    source = unfrackpath(source, follow=False)
                parse = self.parse_source(source, cache=cache)
                if parse and not parsed:
                    parsed = True

        if parsed:
            # do post processing
            self._inventory.reconcile_inventory()
        else:
            display.warning("No inventory was parsed, only implicit localhost is available")

        self._inventory_plugins = []

    def parse_source(self, source, cache=False):
        ''' Generate or update inventory for the source provided '''

        parsed = False
        display.debug(u'Examining possible inventory source: %s' % source)

        b_source = to_bytes(source)
        # process directories as a collection of inventories
        if os.path.isdir(b_source):
            display.debug(u'Searching for inventory files in directory: %s' % source)
            for i in sorted(os.listdir(b_source)):

                display.debug(u'Considering %s' % i)
                # Skip hidden files and stuff we explicitly ignore
                if IGNORED.search(i):
                    continue

                # recursively deal with directory entries
                fullpath = os.path.join(b_source, i)
                parsed_this_one = self.parse_source(to_native(fullpath))
                display.debug(u'parsed %s as %s' % (fullpath, parsed_this_one))
                if not parsed:
                    parsed = parsed_this_one
        else:
            # left with strings or files, let plugins figure it out

            # set so new hosts can use for inventory_file/dir vasr
            self._inventory.current_source = source

            # get inventory plugins if needed, there should always be at least one generator
            if not self._inventory_plugins:
                self._setup_inventory_plugins()

            # try source with each plugin
            failures = []
            for plugin in self._inventory_plugins:
                plugin_name = to_native(getattr(plugin, '_load_name', getattr(plugin, '_original_path', '')))
                display.debug(u'Attempting to use plugin %s (%s)' % (plugin_name, plugin._original_path))

                # initialize and figure out if plugin wants to attempt parsing this file
                try:
                    plugin_wants = bool(plugin.verify_file(source))
                except Exception:
                    plugin_wants = False

                if plugin_wants:
                    try:
                        plugin.parse(self._inventory, self._loader, source, cache=cache)
                        parsed = True
                        display.vvv('Parsed %s inventory source with %s plugin' % (to_text(source), plugin_name))
                        break
                    except AnsibleParserError as e:
                        display.debug('%s was not parsable by %s' % (to_text(source), plugin_name))
                        failures.append({'src': source, 'plugin': plugin_name, 'exc': e})
                    except Exception as e:
                        display.debug('%s failed to parse %s' % (plugin_name, to_text(source)))
                        failures.append({'src': source, 'plugin': plugin_name, 'exc': e})
                else:
                    display.debug('%s did not meet %s requirements' % (to_text(source), plugin_name))
            else:
                if not parsed and failures:
                    # only if no plugin processed files should we show errors.
                    if C.INVENTORY_UNPARSED_IS_FAILED:
                        msg = "Could not parse inventory source %s with available plugins:\n" % source
                        for fail in failures:
                            msg += 'Plugin %s failed: %s\n' % (fail['plugin'], to_native(fail['exc']))
                            if display.verbosity >= 3:
                                msg += "%s\n" % fail['exc'].tb
                        raise AnsibleParserError(msg)
                    else:
                        for fail in failures:
                            display.warning(u'\n* Failed to parse %s with %s plugin: %s' % (to_text(fail['src']), fail['plugin'], to_text(fail['exc'])))
                            display.vvv(to_text(fail['exc'].tb))
        if not parsed:
            display.warning("Unable to parse %s as an inventory source" % to_text(source))

        # clear up, jic
        self._inventory.current_source = None

        return parsed

    def clear_caches(self):
        ''' clear all caches '''
        self._hosts_patterns_cache = {}
        self._pattern_cache = {}
        # FIXME: flush inventory cache

    def refresh_inventory(self):
        ''' recalculate inventory '''

        self.clear_caches()
        self._inventory = InventoryData()
        self.parse_sources(cache=False)

    def _match_list(self, items, pattern_str):
        # compile patterns
        try:
            if not pattern_str.startswith('~'):
                pattern = re.compile(fnmatch.translate(pattern_str))
            else:
                pattern = re.compile(pattern_str[1:])
        except Exception:
            raise AnsibleError('Invalid host list pattern: %s' % pattern_str)

        # apply patterns
        results = []
        for item in items:
            if pattern.match(item):
                results.append(item)
        return results

    def get_hosts(self, pattern="all", ignore_limits=False, ignore_restrictions=False, order=None):
        """
        Takes a pattern or list of patterns and returns a list of matching
        inventory host names, taking into account any active restrictions
        or applied subsets
        """

        # Check if pattern already computed
        if isinstance(pattern, list):
            pattern_hash = u":".join(pattern)
        else:
            pattern_hash = pattern

        if not ignore_limits and self._subset:
            pattern_hash += ":%s" % to_native(self._subset)

        if not ignore_restrictions and self._restriction:
            pattern_hash += ":%s" % to_native(self._restriction)

        if pattern_hash not in self._hosts_patterns_cache:

            patterns = split_host_pattern(pattern)
            hosts = self._evaluate_patterns(patterns)

            # mainly useful for hostvars[host] access
            if not ignore_limits and self._subset:
                # exclude hosts not in a subset, if defined
                subset = self._evaluate_patterns(self._subset)
                hosts = [h for h in hosts if h in subset]

            if not ignore_restrictions and self._restriction:
                # exclude hosts mentioned in any restriction (ex: failed hosts)
                hosts = [h for h in hosts if h.name in self._restriction]

            seen = set()
            self._hosts_patterns_cache[pattern_hash] = [x for x in hosts if x not in seen and not seen.add(x)]

        # sort hosts list if needed (should only happen when called from strategy)
        if order in ['sorted', 'reverse_sorted']:
            from operator import attrgetter
            hosts = sorted(self._hosts_patterns_cache[pattern_hash][:], key=attrgetter('name'), reverse=(order == 'reverse_sorted'))
        elif order == 'reverse_inventory':
            hosts = sorted(self._hosts_patterns_cache[pattern_hash][:], reverse=True)
        else:
            hosts = self._hosts_patterns_cache[pattern_hash][:]
            if order == 'shuffle':
                from random import shuffle
                shuffle(hosts)
            elif order not in [None, 'inventory']:
                AnsibleOptionsError("Invalid 'order' specified for inventory hosts: %s" % order)

        return hosts

    def _evaluate_patterns(self, patterns):
        """
        Takes a list of patterns and returns a list of matching host names,
        taking into account any negative and intersection patterns.
        """

        patterns = order_patterns(patterns)
        hosts = []

        for p in patterns:
            # avoid resolving a pattern that is a plain host
            if p in self._inventory.hosts:
                hosts.append(self._inventory.get_host(p))
            else:
                that = self._match_one_pattern(p)
                if p.startswith("!"):
                    hosts = [h for h in hosts if h not in frozenset(that)]
                elif p.startswith("&"):
                    hosts = [h for h in hosts if h in frozenset(that)]
                else:
                    hosts.extend([h for h in that if h.name not in frozenset([y.name for y in hosts])])
        return hosts

    def _match_one_pattern(self, pattern):
        """
        Takes a single pattern and returns a list of matching host names.
        Ignores intersection (&) and exclusion (!) specifiers.

        The pattern may be:

            1. A regex starting with ~, e.g. '~[abc]*'
            2. A shell glob pattern with ?/*/[chars]/[!chars], e.g. 'foo*'
            3. An ordinary word that matches itself only, e.g. 'foo'

        The pattern is matched using the following rules:

            1. If it's 'all', it matches all hosts in all groups.
            2. Otherwise, for each known group name:
                (a) if it matches the group name, the results include all hosts
                    in the group or any of its children.
                (b) otherwise, if it matches any hosts in the group, the results
                    include the matching hosts.

        This means that 'foo*' may match one or more groups (thus including all
        hosts therein) but also hosts in other groups.

        The built-in groups 'all' and 'ungrouped' are special. No pattern can
        match these group names (though 'all' behaves as though it matches, as
        described above). The word 'ungrouped' can match a host of that name,
        and patterns like 'ungr*' and 'al*' can match either hosts or groups
        other than all and ungrouped.

        If the pattern matches one or more group names according to these rules,
        it may have an optional range suffix to select a subset of the results.
        This is allowed only if the pattern is not a regex, i.e. '~foo[1]' does
        not work (the [1] is interpreted as part of the regex), but 'foo*[1]'
        would work if 'foo*' matched the name of one or more groups.

        Duplicate matches are always eliminated from the results.
        """

        if pattern.startswith("&") or pattern.startswith("!"):
            pattern = pattern[1:]

        if pattern not in self._pattern_cache:
            (expr, slice) = self._split_subscript(pattern)
            hosts = self._enumerate_matches(expr)
            try:
                hosts = self._apply_subscript(hosts, slice)
            except IndexError:
                raise AnsibleError("No hosts matched the subscripted pattern '%s'" % pattern)
            self._pattern_cache[pattern] = hosts

        return self._pattern_cache[pattern]

    def _split_subscript(self, pattern):
        """
        Takes a pattern, checks if it has a subscript, and returns the pattern
        without the subscript and a (start,end) tuple representing the given
        subscript (or None if there is no subscript).

        Validates that the subscript is in the right syntax, but doesn't make
        sure the actual indices make sense in context.
        """

        # Do not parse regexes for enumeration info
        if pattern.startswith('~'):
            return (pattern, None)

        # We want a pattern followed by an integer or range subscript.
        # (We can't be more restrictive about the expression because the
        # fnmatch semantics permit [\[:\]] to occur.)

        pattern_with_subscript = re.compile(
            r'''^
                (.+)                    # A pattern expression ending with...
                \[(?:                   # A [subscript] expression comprising:
                    (-?[0-9]+)|         # A single positive or negative number
                    ([0-9]+)([:-])      # Or an x:y or x: range.
                    ([0-9]*)
                )\]
                $
            ''', re.X
        )

        subscript = None
        m = pattern_with_subscript.match(pattern)
        if m:
            (pattern, idx, start, sep, end) = m.groups()
            if idx:
                subscript = (int(idx), None)
            else:
                if not end:
                    end = -1
                subscript = (int(start), int(end))
                if sep == '-':
                    display.warning("Use [x:y] inclusive subscripts instead of [x-y] which has been removed")

        return (pattern, subscript)

    def _apply_subscript(self, hosts, subscript):
        """
        Takes a list of hosts and a (start,end) tuple and returns the subset of
        hosts based on the subscript (which may be None to return all hosts).
        """

        if not hosts or not subscript:
            return hosts

        (start, end) = subscript

        if end:
            if end == -1:
                end = len(hosts) - 1
            return hosts[start:end + 1]
        else:
            return [hosts[start]]

    def _enumerate_matches(self, pattern):
        """
        Returns a list of host names matching the given pattern according to the
        rules explained above in _match_one_pattern.
        """

        results = []
        # check if pattern matches group
        matching_groups = self._match_list(self._inventory.groups, pattern)
        if matching_groups:
            for groupname in matching_groups:
                results.extend(self._inventory.groups[groupname].get_hosts())

        # check hosts if no groups matched or it is a regex/glob pattern
        if not matching_groups or pattern.startswith('~') or any(special in pattern for special in ('.', '?', '*', '[')):
            # pattern might match host
            matching_hosts = self._match_list(self._inventory.hosts, pattern)
            if matching_hosts:
                for hostname in matching_hosts:
                    results.append(self._inventory.hosts[hostname])

        if not results and pattern in C.LOCALHOST:
            # get_host autocreates implicit when needed
            implicit = self._inventory.get_host(pattern)
            if implicit:
                results.append(implicit)

        if not results and pattern != 'all':
            display.warning("Could not match supplied host pattern, ignoring: %s" % pattern)
        return results

    def list_hosts(self, pattern="all"):
        """ return a list of hostnames for a pattern """
        # FIXME: cache?
        result = [h for h in self.get_hosts(pattern)]

        # allow implicit localhost if pattern matches and no other results
        if len(result) == 0 and pattern in C.LOCALHOST:
            result = [pattern]

        return result

    def list_groups(self):
        # FIXME: cache?
        return sorted(self._inventory.groups.keys(), key=lambda x: x)

    def restrict_to_hosts(self, restriction):
        """
        Restrict list operations to the hosts given in restriction.  This is used
        to batch serial operations in main playbook code, don't use this for other
        reasons.
        """
        if restriction is None:
            return
        elif not isinstance(restriction, list):
            restriction = [restriction]
        self._restriction = [h.name for h in restriction]

    def subset(self, subset_pattern):
        """
        Limits inventory results to a subset of inventory that matches a given
        pattern, such as to select a given geographic of numeric slice amongst
        a previous 'hosts' selection that only select roles, or vice versa.
        Corresponds to --limit parameter to ansible-playbook
        """
        if subset_pattern is None:
            self._subset = None
        else:
            subset_patterns = split_host_pattern(subset_pattern)
            results = []
            # allow Unix style @filename data
            for x in subset_patterns:
                if x.startswith("@"):
                    fd = open(x[1:])
                    results.extend(fd.read().split("\n"))
                    fd.close()
                else:
                    results.append(x)
            self._subset = results

    def remove_restriction(self):
        """ Do not restrict list operations """
        self._restriction = None

    def clear_pattern_cache(self):
        self._pattern_cache = {}
