# Copyright (c) 2016-2017 Hewlett Packard Enterprise Development LP
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import sys
from ansible.compat.tests.mock import patch, Mock

sys.modules['hpOneView'] = Mock()
sys.modules['hpOneView.oneview_client'] = Mock()
sys.modules['future'] = Mock()
sys.modules['__future__'] = Mock()

ONEVIEW_MODULE_UTILS_PATH = 'ansible.module_utils.oneview'
from ansible.module_utils.oneview import (OneViewModuleException,
                                          OneViewModuleTaskError,
                                          OneViewModuleResourceNotFound,
                                          OneViewModuleBase)

from ansible.modules.remote_management.oneview.oneview_ethernet_network import EthernetNetworkModule
from ansible.modules.remote_management.oneview.oneview_ethernet_network_facts import EthernetNetworkFactsModule
from ansible.modules.remote_management.oneview.oneview_fc_network import FcNetworkModule
from ansible.modules.remote_management.oneview.oneview_fc_network_facts import FcNetworkFactsModule
from ansible.modules.remote_management.oneview.oneview_fcoe_network import FcoeNetworkModule
from ansible.modules.remote_management.oneview.oneview_fcoe_network_facts import FcoeNetworkFactsModule
from ansible.modules.remote_management.oneview.oneview_network_set import NetworkSetModule
from ansible.modules.remote_management.oneview.oneview_network_set_facts import NetworkSetFactsModule
from ansible.modules.remote_management.oneview.oneview_san_manager import SanManagerModule
