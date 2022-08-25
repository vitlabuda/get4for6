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
from datalidator.blueprints.impl.ObjectBlueprint import ObjectBlueprint
from get4for6.config.loader._GeneralConfigurationModel import _GeneralConfigurationModel
from get4for6.config.loader._TranslationConfigurationModel import _TranslationConfigurationModel
from get4for6.config.loader._TranslationConfigurationValidator import _TranslationConfigurationValidator
from get4for6.config.loader._TundraExternalAddrXlatConfigurationModel import _TundraExternalAddrXlatConfigurationModel
from get4for6.config.loader._TundraExternalAddrXlatConfigurationValidator import _TundraExternalAddrXlatConfigurationValidator
from get4for6.config.loader._DNSConfigurationModel import _DNSConfigurationModel
from get4for6.config.loader._SimpleAddrQueryConfigurationModel import _SimpleAddrQueryConfigurationModel
from get4for6.config.loader._SimpleAddrQueryConfigurationValidator import _SimpleAddrQueryConfigurationValidator
from get4for6.config.loader._PassDictFurtherIfEnabledBlueprint import _PassDictFurtherIfEnabledBlueprint


class _ConfigurationModel(ObjectModel):
    general = ObjectBlueprint(
        _GeneralConfigurationModel,
        tag="general"
    )

    translation = ObjectBlueprint(
        _TranslationConfigurationModel,
        validators=(
            _TranslationConfigurationValidator(tag="translation"),
        ),
        tag="translation"
    )

    tundra_external_addr_xlat = ObjectBlueprint(
        _TundraExternalAddrXlatConfigurationModel,
        validators=(
            _TundraExternalAddrXlatConfigurationValidator(tag="tundra_external_addr_xlat"),
        ),
        tag="tundra_external_addr_xlat"
    )

    dns = _PassDictFurtherIfEnabledBlueprint(
        pass_to_blueprint=ObjectBlueprint(
            _DNSConfigurationModel,
            tag="dns"
        ),
        return_if_disabled=None,
        tag="dns"
    )

    simple_addr_query = _PassDictFurtherIfEnabledBlueprint(
        pass_to_blueprint=ObjectBlueprint(
            _SimpleAddrQueryConfigurationModel,
            validators=(
                _SimpleAddrQueryConfigurationValidator(tag="simple_addr_query"),
            ),
            tag="simple_addr_query"
        ),
        return_if_disabled=None,
        tag="simple_addr_query"
    )
