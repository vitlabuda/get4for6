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


from datalidator.blueprints.extras.ObjectModel import ObjectModel
from datalidator.blueprints.impl.BooleanBlueprint import BooleanBlueprint
from datalidator.blueprints.impl.StringBlueprint import StringBlueprint
from datalidator.blueprints.impl.ListBlueprint import ListBlueprint
from datalidator.blueprints.impl.IPAddressBlueprint import IPAddressBlueprint
from datalidator.filters.impl.StringStripFilter import StringStripFilter
from datalidator.filters.impl.StringLowercaseFilter import StringLowercaseFilter
from datalidator.validators.impl.StringMatchesRegexValidator import StringMatchesRegexValidator
from datalidator.validators.impl.StringContainsSubstringValidator import StringContainsSubstringValidator
from datalidator.validators.impl.SequenceHasAllItemsUniqueValidator import SequenceHasAllItemsUniqueValidator
from get4for6.config.loader._IPAddressContainsNoScopeIDValidator import _IPAddressContainsNoScopeIDValidator


class _AuxiliaryNamesModel(ObjectModel):
    domain = StringBlueprint(
        filters=(
            StringStripFilter(tag="domain"),
            StringLowercaseFilter(tag="domain")
        ),
        validators=(
            StringMatchesRegexValidator(r'^([0-9a-z-]+\.)+\Z', tag="domain"),
            StringMatchesRegexValidator(r'^-', negate=True, tag="domain"),
            StringContainsSubstringValidator("-.", negate=True, tag="domain"),
            StringContainsSubstringValidator(".-", negate=True, tag="domain")
        ),
        tag="domain"
    )

    use_for_rdns = BooleanBlueprint(tag="use_for_rdns")

    zone_ns_ips = ListBlueprint(
        item_blueprint=IPAddressBlueprint(
            validators=(_IPAddressContainsNoScopeIDValidator(tag="zone_ns_ips"),),
            tag="zone_ns_ips"
        ),
        validators=(SequenceHasAllItemsUniqueValidator(tag="zone_ns_ips"),),
        tag="zone_ns_ips"
    )
