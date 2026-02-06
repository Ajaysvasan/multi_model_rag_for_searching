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


def get_least_occuring_node(cache: OrderedDict, level: int):
    node: CacheNode = CacheNode()
    return node


class TopicCacheManager:
    recency_boost: float
    l1_cache_count: int
    l2_cache_count: int
    l3_cache_count: int
    l3_least_occurace_node: CacheNode
    l2_least_occurace_node: CacheNode
    l1_least_occurace_node: CacheNode

    def __init__(self) -> None:
        self.recency_boost = Config.RECENCY_BOOST
        cache_loader.load_cache()
        self.l1_cache_count, self.l2_cache_count, self.l3_cache_count = (
            cache_loader.get_cache_count()
        )
        self.l3_least_occurace_node = get_least_occuring_node(CACHE, level=3)
        self.l2_least_occurace_node = get_least_occuring_node(CACHE, level=2)
        self.l1_least_occurace_node = get_least_occuring_node(CACHE, level=1)
        CACHE.move_to_end(self.l3_least_occurace_node)

    def _get_key_(self, node: CacheNode) -> TopicKey:
        target_key: TopicKey
        for key, value in CACHE.items():
            if value == node:
                target_key = key
        return target_key

    def _promote(self, topic_key: TopicKey, score: float):

        node: CacheNode = CACHE[topic_key]
        # 3 -> 2 -> 1
        node.level -= 1
        if score > Config.L2_THRESHOLD and self.l2_cache_count < Config.L2_CAPACITY:
            self.l2_cache_count += 1
            self.l3_cache_count -= 1
            self.l2_least_occurace_node = node
            CACHE[topic_key] = node
            # TODO: Here we also update the DB so that on the next load the updaed cache is loaded
            return 0
        if score > Config.L1_THRESHOLD and self.l1_cache_count < Config.L1_CAPACITY:
            self.l1_cache_count += 1
            self.l2_cache_count -= 1
            CACHE[topic_key] = node
            self.l1_least_occurace_node = node
            # TODO: Here we also update the DB so that on the next load the updaed cache is loaded
            return 0

        if score > Config.L2_THRESHOLD:
            curr_level_least_occurance_node = self._get_key_(
                self.l2_least_occurace_node
            )
            CACHE[curr_level_least_occurance_node].level += 1
            self.l2_cache_count -= 1
            CACHE[topic_key] = node

            # TODO: Here we also update the DB so that on the next load the updaed cache is loaded
            return 0

        if score > Config.L1_THRESHOLD:
            curr_level_least_occurance_node = self._get_key_(
                self.l1_least_occurace_node
            )
            CACHE[curr_level_least_occurance_node].level += 1
            self.l1_cache_count -= 1
            CACHE[topic_key] = node
            return 0
        # TODO: Here we also update the DB so that on the next load the updaed cache is loaded

    def _demote(self, node: CacheNode):
        # 3 <- 2 <- 1
        curr_node_key = self._get_key_(node)
        CACHE[curr_node_key].level += 1
        if node.level == 1 and self.l2_cache_count < Config.L2_CAPACITY:
            self.l1_cache_count -= 1
            self.l2_cache_count += 1
            return 0
            # TODO: Here we also update the DB so that on the next load the updaed cache is loaded
        if node.level == 2 and self.l3_cache_count < Config.L3_CAPACITY:
            self.l2_cache_count -= 1
            self.l3_cache_count += 1
            return 0
            # TODO: Here we also update the DB so that on the next load the updaed cache is loaded

        if len(CACHE) == Config.L1_CAPACITY + Config.L2_CAPACITY + Config.L3_CAPACITY:
            self._remove_topic()

        if (
            node.level == 1
            and self.l2_cache_count == Config.L2_CAPACITY
            and self.l3_cache_count < Config.L3_CAPACITY
        ):
            l2_least_occurace_node_key = self._get_key_(self.l2_least_occurace_node)
            CACHE[l2_least_occurace_node_key].level += 1
            self.l1_cache_count -= 1
            self.l2_cache_count += 1
            self.l3_cache_count += 1
            return 0
        if node.level == 2 and self.l3_cache_count < Config.L3_CAPACITY:
            l2_least_occurace_node_key = self._get_key_(self.l2_least_occurace_node)
            CACHE[l2_least_occurace_node_key].level += 1
            self.l2_cache_count -= 1
            self.l3_cache_count += 1
            return 0

    def _remove_topic(self):
        CACHE.popitem()

    def lookup(self, key: TopicKey):
        # Return the state if the TopicKey is found in the Dict
        try:
            # Checking if the topic of interest is in the current conversation window
            node: CacheNode = CACHE[key]
            node.state.access_count += 1
            if node.level != 0:
                score = node.state.access_count * 0.7 + self.recency_boost * 0.3
                if (node.level == 2 and score > Config.L1_THRESHOLD) or (
                    node.level == 3 and score > Config.L2_THRESHOLD
                ):
                    self._promote(key, score)
                if node.level == 2 and score < Config.L2_THRESHOLD:
                    self._demote(node)
                if (
                    node.level == 3
                    and score < Config.L3_THRESHOLD
                    and self.l3_cache_count == Config.L3_CAPACITY
                ):
                    self._remove_topic()

            CACHE[key] = node
            return node
        except:
            # The logic for conversation history checking goes here
            # returns -1 indicating that the operation is not successful indicating that the node is not in any of the current cache after searching in the context history
            return -1

    def insert(self, key: TopicKey, state: TopicState):
        # here by default the new topic enters into the L3 cache
        if self.l3_cache_count == Config.L3_CAPACITY:
            self._remove_topic()
            CACHE[key] = state
        else:
            CACHE[key] = state


if __name__ == "__main__":
    topic_manager = TopicCacheManager()
    key: TopicKey = TopicKey("os", ".pdf", "")
    if topic_manager.lookup(key) != 0:
        print(f"The node is found")
    else:
        print(f"The node is not found")
