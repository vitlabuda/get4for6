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


from typing import Final, List, Any, Optional, Tuple, Type, Sequence
import ipaddress
import socket
from datalidator.blueprints.DefaultBlueprintWithStandardFeaturesImplBase import DefaultBlueprintWithStandardFeaturesImplBase
from datalidator.blueprints.impl.ListBlueprint import ListBlueprint
from datalidator.blueprints.impl.StringBlueprint import StringBlueprint
from datalidator.blueprints.impl.IntegerBlueprint import IntegerBlueprint
from datalidator.blueprints.impl.IPAddressBlueprint import IPAddressBlueprint
from datalidator.blueprints.exc.BlueprintExc import BlueprintExc
from datalidator.filters.FilterIface import FilterIface
from datalidator.filters.impl.StringStripFilter import StringStripFilter
from datalidator.filters.impl.ListDeduplicateItemsFilter import ListDeduplicateItemsFilter
from datalidator.validators.ValidatorIface import ValidatorIface
from datalidator.validators.impl.SequenceIsNotEmptyValidator import SequenceIsNotEmptyValidator
from datalidator.validators.impl.SequenceMinimumLengthValidator import SequenceMinimumLengthValidator
from datalidator.validators.impl.SequenceMaximumLengthValidator import SequenceMaximumLengthValidator
from datalidator.validators.impl.IPAddressIsInNetworkValidator import IPAddressIsInNetworkValidator
from datalidator.validators.impl.IPAddressIsMulticastValidator import IPAddressIsMulticastValidator
from datalidator.validators.impl.NumberMinimumValueValidator import NumberMinimumValueValidator
from datalidator.validators.impl.NumberMaximumValueValidator import NumberMaximumValueValidator
from get4for6.config.IPPortPair import IPPortPair


class _IPPortPairListBlueprint(DefaultBlueprintWithStandardFeaturesImplBase[List[IPPortPair]]):
    # WARNING: This blueprint does not follow the best-practice of being environment-agnostic, as it resolves host and
    #  service names to IP addresses and ports using the 'socket.getaddrinfo()' function, and therefore accesses
    #  external resources ('/etc/hosts', '/etc/resolv.conf', '/etc/services', DNS, ...)!

    class NameResolutionFailureInBlueprintExc(BlueprintExc):
        # It is not possible to raise 'NameResolutionFailureExc' in this blueprint, as it is not a subclass of 'DatalidatorExc'.

        def __init__(self, host_name: str, service_name: str, reason: str, originator_tag: str):
            BlueprintExc.__init__(self, f"Failed to resolve {repr((host_name, service_name))}: {reason}", originator_tag)

            self._host_name: Final[str] = host_name
            self._service_name: Final[str] = service_name
            self._reason: Final[str] = reason

        @property
        def host_name(self) -> str:
            return self._host_name

        @property
        def service_name(self) -> str:
            return self._service_name

        @property
        def reason(self) -> str:
            return self._reason

    def __init__(self,
                 filters: Sequence[FilterIface[List[IPPortPair]]] = (),
                 validators: Sequence[ValidatorIface[List[IPPortPair]]] = (),
                 tag: str = ""):
        DefaultBlueprintWithStandardFeaturesImplBase.__init__(
            self=self,
            filters=((ListDeduplicateItemsFilter(),) + tuple(filters)),
            validators=validators,
            tag=tag
        )

        self._host_service_pair_list_blueprint: Final[ListBlueprint] = ListBlueprint(
            item_blueprint=ListBlueprint(
                item_blueprint=StringBlueprint(
                    filters=(StringStripFilter(tag=tag),),
                    validators=(SequenceIsNotEmptyValidator(tag=tag),),
                    tag=tag
                ),
                validators=(
                    SequenceMinimumLengthValidator(2, tag=tag),
                    SequenceMaximumLengthValidator(2, tag=tag)
                ),
                tag=tag
            ),
            tag=tag
        )

        self._ip_blueprint: Final[IPAddressBlueprint] = IPAddressBlueprint(
            validators=(
                IPAddressIsMulticastValidator(negate=True, tag=tag),
                IPAddressIsInNetworkValidator(ipaddress.IPv4Network("255.255.255.255/32"), negate=True, tag=tag)
            ),
            tag=tag
        )

        self._port_blueprint: Final[IntegerBlueprint] = IntegerBlueprint(
            validators=(
                NumberMinimumValueValidator(1, tag=tag),
                NumberMaximumValueValidator(65535, tag=tag)
            ),
            tag=tag
        )

    def _get_allowed_output_data_types(self) -> Optional[Tuple[Type, ...]]:
        return list,

    def _parse(self, input_data: Any) -> List[IPPortPair]:
        # Exceptions are not caught here -> they propagate up the stack
        host_service_pair_list = self._host_service_pair_list_blueprint.use(input_data)

        ip_port_pair_list = []
        for host_service_pair in host_service_pair_list:
            ip_port_pair_list += self._resolve_host_service_pair(host_name=host_service_pair[0], service_name=host_service_pair[1])

        return ip_port_pair_list

    def _resolve_host_service_pair(self, host_name: str, service_name: str) -> List[IPPortPair]:
        # https://docs.python.org/3/library/socket.html#socket.getaddrinfo
        try:
            getaddrinfo_results = socket.getaddrinfo(
                host=host_name,
                port=service_name,
                family=socket.AF_UNSPEC,
                type=0,
                proto=0,
                flags=0
            )
        except OSError as e:
            raise self.__class__.NameResolutionFailureInBlueprintExc(host_name, service_name, str(e), self._tag)

        if not getaddrinfo_results:  # = If the result list is empty
            raise self.__class__.NameResolutionFailureInBlueprintExc(host_name, service_name, "getaddrinfo() succeeded, but it returned an empty result list!", self._tag)

        return [IPPortPair(
            # Exceptions are not caught here -> they propagate up the stack
            ip_address=self._ip_blueprint.use(result[4][0]),
            port=self._port_blueprint.use(result[4][1])
        ) for result in getaddrinfo_results]
