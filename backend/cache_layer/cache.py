"""Cache module"""

import os
import sys
from collections import OrderedDict

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from load_cache import cache_loader
from TopicState import TopicKey, TopicState

from config import Config

# Contains  the caches L1 , L2 , L3 in the same order has their respective range
# Dict structure : {TopicKey: CacheNode}
CACHE = OrderedDict()


# Three levels L1 -> Hot cache , L2 -> Warm cache and L3 -> cold cache
class CacheNode:
    key: TopicKey
    state: TopicState
    level: int
