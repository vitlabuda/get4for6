#!/bin/false

# Copyright (c) 2022 Vít Labuda. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#  1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#     disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#     following disclaimer in the documentation and/or other materials provided with the distribution.
#  3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
#     products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from typing import Final, Optional, Iterator, Union, Generator
import time
import ipaddress
import sortedcontainers
from get4for6.exc.ThisShouldNeverHappenExc import ThisShouldNeverHappenExc
from get4for6.addr_mapper.substitute._DynamicAddressAssignment import _DynamicAddressAssignment
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.addr_mapper.substitute.exc.SubstituteAddressSpaceCurrentlyFullExc import SubstituteAddressSpaceCurrentlyFullExc
from get4for6.helpers.IPHelpers import IPHelpers


class _DynamicSubstituteAddressMapper:
    """
    Takes care of dynamic substitute address assignments, and maps them in both directions (4to6, 6to4).
    """

    # Even short-term caching improves performance greatly, and is far less prone to problems than caching for longer
    #  periods of time.
    _EXTERNAL_CACHE_LIFETIME_LIMIT: Final[int] = 10

    def __init__(self, substitute_subnets: tuple[ipaddress.IPv4Network, ...], do_not_assign: frozenset[ipaddress.IPv4Address], min_lifetime_after_last_hit: int):
        """
        It is assumed that the supplied arguments are valid. Under normal circumstances, the necessary validity checks
         are carried out by this program's configuration loading procedures.
        """

        assert (min_lifetime_after_last_hit >= 0)

        self._dynamic_map: Final[dict[Union[ipaddress.IPv4Address, ipaddress.IPv6Address], _DynamicAddressAssignment]] = dict()
        self._replacement_queue: Final[sortedcontainers.SortedDict[int, set[ipaddress.IPv4Address]]] = sortedcontainers.SortedDict()
        self._min_lifetime_after_last_hit: Final[int] = min_lifetime_after_last_hit
        self._external_cache_lifetime: Final[int] = self._calculate_external_cache_lifetime_from_min_lifetime_after_last_hit(min_lifetime_after_last_hit)

        self._iterator_of_ipv4s_to_assign: Optional[Iterator[ipaddress.IPv4Address]] = iter(self._generator_of_ipv4s_to_assign(
            substitute_subnets=substitute_subnets,
            do_not_assign=do_not_assign
        ))

    def get_external_cache_lifetime(self) -> int:
        return self._external_cache_lifetime

    def _generator_of_ipv4s_to_assign(self, substitute_subnets: tuple[ipaddress.IPv4Network, ...], do_not_assign: frozenset[ipaddress.IPv4Address]) -> Iterator[ipaddress.IPv4Address]:
        for subnet in substitute_subnets:
            for address in subnet:
                if (address in do_not_assign) or IPHelpers.is_ipv4_address_the_network_or_broadcast_address_of_subnet(address, subnet):
                    continue
                yield address

    def _calculate_external_cache_lifetime_from_min_lifetime_after_last_hit(self, min_lifetime_after_last_hit: int) -> int:
        # When a dynamic assignment is being cached by an external program, this program cannot know whether it is being
        #  hit or not. Therefore, dynamic assignments may be cached only for one third of their minimum guaranteed
        #  lifetime minus one second. This ensures that there is a sufficient time window, in which the external program
        #  will query this program for the dynamic assignment if it still uses it, which means that the hit will get
        #  registered and the lifetime of the assignment extended.
        external_cache_lifetime = int((min_lifetime_after_last_hit / 3.0) - 1.0)

        return max(min(external_cache_lifetime, self.__class__._EXTERNAL_CACHE_LIFETIME_LIMIT), 0)  # Perform the necessary clamping

    def find_substitute_assignment_4to6(self, valid_ipv4_address: ipaddress.IPv4Address) -> ipaddress.IPv6Address:
        """
        :raises SubstituteAssignmentNotFoundExc
        """

        assert isinstance(valid_ipv4_address, ipaddress.IPv4Address)  # Make sure that nothing is broken (and nothing will break)

        return self._find_substitute_assignment(valid_ipv4_address).ipv6_address

    def find_or_create_substitute_assignment_6to4(self, valid_ipv6_address: ipaddress.IPv6Address, creation_allowed: bool) -> ipaddress.IPv4Address:
        """
        :raises SubstituteAssignmentNotFoundExc
        :raises SubstituteAddressSpaceCurrentlyFullExc
        """

        assert isinstance(valid_ipv6_address, ipaddress.IPv6Address)  # Make sure that nothing is broken (and nothing will break)

        # Try to find an existing assignment...
        try:
            return self._find_substitute_assignment(valid_ipv6_address).ipv4_address
        except SubstituteAssignmentNotFoundExc:
            pass

        # ... and if it does not exist, try to create a new one.
        if not creation_allowed:
            raise SubstituteAssignmentNotFoundExc(valid_ipv6_address)

        if not IPHelpers.is_ipv6_address_substitutable(valid_ipv6_address):
            raise ThisShouldNeverHappenExc(f"The IPv6 address {valid_ipv6_address} should have already been validated!")

        new_assignment_object = self._create_and_add_assignment_with_new_ipv4_if_possible(valid_ipv6_address)
        if new_assignment_object is None:
            new_assignment_object = self._create_and_add_assignment_with_recycled_ipv4(valid_ipv6_address)

        return new_assignment_object.ipv4_address

    def _create_and_add_assignment_with_new_ipv4_if_possible(self, valid_ipv6_address: ipaddress.IPv6Address) -> Optional[_DynamicAddressAssignment]:
        if self._iterator_of_ipv4s_to_assign is None:
            return None

        try:
            ipv4_address = next(self._iterator_of_ipv4s_to_assign)
        except StopIteration:
            self._iterator_of_ipv4s_to_assign = None
            return None

        assignment_object = _DynamicAddressAssignment(
            ipv4_address=ipv4_address,
            ipv6_address=valid_ipv6_address,
            last_hit_at=self._get_current_timestamp()
        )
        self._add_assignment(assignment_object)
        return assignment_object

    def _create_and_add_assignment_with_recycled_ipv4(self, valid_ipv6_address: ipaddress.IPv6Address) -> _DynamicAddressAssignment:
        assert (self._iterator_of_ipv4s_to_assign is None)

        try:
            # The items in 'SortedDict' are (automatically) sorted by their keys, which correspond to the
            #  'last_hit' timestamp; therefore, this statement always returns (without modifying the queue) the dynamic
            #  assignment which is "the most likely to be abandoned"
            last_hit_at_from_replacement_queue, old_set = self._replacement_queue.peekitem(0)
        except IndexError:
            # Can happen if the whole substitute address space is reserved by static assignments
            raise SubstituteAddressSpaceCurrentlyFullExc()

        # Unfortunately, there seems to be no better way of getting an arbitrary item from a set without modifying it
        old_assignment_object = self._dynamic_map[next(iter(old_set))]
        assert (last_hit_at_from_replacement_queue == old_assignment_object.last_hit_at)

        if (self._get_current_timestamp() - old_assignment_object.last_hit_at) < self._min_lifetime_after_last_hit:
            raise SubstituteAddressSpaceCurrentlyFullExc()

        # Up until now (in this method), the state of this class's instance variables has not been mutated
        self._remove_assignment(old_assignment_object)

        new_assignment_object = _DynamicAddressAssignment(
            ipv4_address=old_assignment_object.ipv4_address,
            ipv6_address=valid_ipv6_address,
            last_hit_at=self._get_current_timestamp()
        )
        self._add_assignment(new_assignment_object)
        return new_assignment_object

    def _find_substitute_assignment(self, find_by: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> _DynamicAddressAssignment:
        try:
            assignment_object = self._dynamic_map[find_by]
        except KeyError:
            raise SubstituteAssignmentNotFoundExc(find_by)

        self._register_hit_of_assignment(assignment_object)
        return assignment_object

    def _register_hit_of_assignment(self, assignment_object: _DynamicAddressAssignment) -> None:
        self._remove_assignment_from_replacement_queue(assignment_object)
        assignment_object.last_hit_at = self._get_current_timestamp()
        self._add_assignment_to_replacement_queue(assignment_object)

    def _add_assignment(self, assignment_object: _DynamicAddressAssignment) -> None:
        ipv4_key = assignment_object.ipv4_address
        ipv6_key = assignment_object.ipv6_address
        assert ((ipv4_key not in self._dynamic_map) and (ipv6_key not in self._dynamic_map))

        self._dynamic_map[ipv4_key] = assignment_object
        self._dynamic_map[ipv6_key] = assignment_object
        self._add_assignment_to_replacement_queue(assignment_object)

    def _remove_assignment(self, assignment_object: _DynamicAddressAssignment) -> None:
        del self._dynamic_map[assignment_object.ipv4_address]  # Fails if the key is not present (should never happen)
        del self._dynamic_map[assignment_object.ipv6_address]  # Fails if the key is not present (should never happen)
        self._remove_assignment_from_replacement_queue(assignment_object)

    def _add_assignment_to_replacement_queue(self, assignment_object: _DynamicAddressAssignment) -> None:
        key = assignment_object.last_hit_at
        added_item = assignment_object.ipv4_address

        if key in self._replacement_queue:
            added_to_set = self._replacement_queue[key]
            assert (added_to_set and (added_item not in added_to_set))
            added_to_set.add(added_item)
        else:
            self._replacement_queue[key] = {added_item}

    def _remove_assignment_from_replacement_queue(self, assignment_object: _DynamicAddressAssignment) -> None:
        key = assignment_object.last_hit_at

        removed_from_set = self._replacement_queue[key]  # Fails if the key is not present
        removed_from_set.remove(assignment_object.ipv4_address)  # Fails if the IPv4 address is not present
        if not removed_from_set:
            del self._replacement_queue[key]

    def _get_current_timestamp(self) -> int:
        timestamp = int(time.clock_gettime(time.CLOCK_MONOTONIC_RAW))
        assert (timestamp >= 0)
        return timestamp

    def send_dynamic_mappings_to_generator(self, generator: Generator[None, tuple[ipaddress.IPv4Address, ipaddress.IPv4Address, ipaddress.IPv6Address, int], None], client_ipv4: ipaddress.IPv4Address) -> None:
        current_timestamp = self._get_current_timestamp()

        for set_from_queue in self._replacement_queue.values():  # The replacement queue is ordered, whereas the dynamic map is not
            for map_search_key in set_from_queue:
                assignment_object = self._dynamic_map[map_search_key]
                remaining_guaranteed_lifetime = max(0, (assignment_object.last_hit_at + self._min_lifetime_after_last_hit) - current_timestamp)

                # This approach of sending address assignments into a generator has the advantage of protecting this
                #  mapper's internal state (mutable instance variables are not exposed to the outside - only
                #  immutable objects are sent to the generator), without it being necessary to copy the possibly huge
                #  dynamic map.
                generator.send((
                    client_ipv4,
                    assignment_object.ipv4_address,
                    assignment_object.ipv6_address,
                    remaining_guaranteed_lifetime
                ))
