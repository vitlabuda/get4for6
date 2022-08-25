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


from typing import Final, Optional, Tuple, Type, Any, Sequence
import ipaddress
from datalidator.blueprints.DefaultBlueprintWithStandardFeaturesImplBase import DefaultBlueprintWithStandardFeaturesImplBase
from datalidator.blueprints.impl.ListBlueprint import ListBlueprint
from datalidator.blueprints.impl.IPAddressBlueprint import IPAddressBlueprint
from datalidator.filters.FilterIface import FilterIface
from datalidator.validators.ValidatorIface import ValidatorIface
from datalidator.validators.impl.SequenceMinimumLengthValidator import SequenceMinimumLengthValidator
from datalidator.validators.impl.SequenceMaximumLengthValidator import SequenceMaximumLengthValidator
from datalidator.validators.impl.IPAddressIsIPv4Validator import IPAddressIsIPv4Validator
from datalidator.validators.impl.IPAddressIsIPv6Validator import IPAddressIsIPv6Validator
from datalidator.validators.impl.IPAddressIsInNetworkValidator import IPAddressIsInNetworkValidator
from datalidator.validators.impl.IPAddressIsLoopbackValidator import IPAddressIsLoopbackValidator
from datalidator.validators.impl.IPAddressIsMulticastValidator import IPAddressIsMulticastValidator
from get4for6.config.loader._IPAddressContainsNoScopeIDValidator import _IPAddressContainsNoScopeIDValidator


class _StaticSubstituteAddrAssignmentBlueprint(DefaultBlueprintWithStandardFeaturesImplBase[Tuple[ipaddress.IPv4Address, ipaddress.IPv6Address]]):
    def __init__(self, filters: Sequence[FilterIface[Tuple[ipaddress.IPv4Address, ipaddress.IPv6Address]]] = (),
                 validators: Sequence[ValidatorIface[Tuple[ipaddress.IPv4Address, ipaddress.IPv6Address]]] = (),
                 tag: str = ""):
        DefaultBlueprintWithStandardFeaturesImplBase.__init__(self, filters, validators, tag)

        self._pair_blueprint: Final[ListBlueprint] = ListBlueprint(
            item_blueprint=IPAddressBlueprint(tag=tag),
            validators=(
                SequenceMinimumLengthValidator(2, tag=tag),
                SequenceMaximumLengthValidator(2, tag=tag)
            ),
            tag=tag
        )

        self._ipv4_blueprint: Final[IPAddressBlueprint] = IPAddressBlueprint(
            validators=(
                IPAddressIsIPv4Validator(tag=tag),
                IPAddressIsLoopbackValidator(negate=True, tag=tag),
                IPAddressIsMulticastValidator(negate=True, tag=tag),
                IPAddressIsInNetworkValidator(ipaddress.IPv4Network("0.0.0.0/8"), negate=True, tag=tag),
                IPAddressIsInNetworkValidator(ipaddress.IPv4Network("255.255.255.255/32"), negate=True, tag=tag)
            ),
            tag=tag
        )

        self._ipv6_blueprint: Final[IPAddressBlueprint] = IPAddressBlueprint(
            validators=(
                IPAddressIsIPv6Validator(tag=tag),
                IPAddressIsLoopbackValidator(negate=True, tag=tag),
                IPAddressIsMulticastValidator(negate=True, tag=tag),
                IPAddressIsInNetworkValidator(ipaddress.IPv6Network("::/128"), negate=True, tag=tag),
                _IPAddressContainsNoScopeIDValidator(tag=tag)
            ),
            tag=tag
        )

    def _get_allowed_output_data_types(self) -> Optional[Tuple[Type, ...]]:
        return tuple,

    def _parse(self, input_data: Any) -> Tuple[ipaddress.IPv4Address, ipaddress.IPv6Address]:
        # Exceptions are not caught here -> they propagate up the stack
        ip_pair = self._pair_blueprint.use(input_data)

        ipv4_address = self._ipv4_blueprint.use(ip_pair[0])
        ipv6_address = self._ipv6_blueprint.use(ip_pair[1])

        return ipv4_address, ipv6_address
