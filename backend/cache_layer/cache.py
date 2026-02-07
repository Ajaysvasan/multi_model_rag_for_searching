import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional

from config import Config

from .TopicState import TopicKey, TopicState


@dataclass
class CacheNode:
    key: TopicKey
    state: TopicState
    level: int  # 1, 2, or 3


class CacheLoader:
    def _check_cache_table(self):
        return False

    def _load_cache(self):
        # Bunch of placeholders for now
        L1: OrderedDict[TopicKey, CacheNode] = OrderedDict()
        L2: OrderedDict[TopicKey, CacheNode] = OrderedDict()
        L3: OrderedDict[TopicKey, CacheNode] = OrderedDict()
        return L1, L2, L3


class TopicCacheManager(CacheLoader):
    def __init__(
        self,
    ):
        self.cap_l1 = Config.L1_CAPACITY
        self.cap_l2 = Config.L2_CAPACITY
        self.cap_l3 = Config.L3_CAPACITY

        self.L3_THRESHOLD = Config.L3_THRESHOLD
        self.L2_THRESHOLD = Config.L2_THRESHOLD

        # Structures
        if not self._check_cache_table():
            self.directory: Dict[TopicKey, CacheNode] = {}

            self.L1: OrderedDict[TopicKey, CacheNode] = OrderedDict()
            self.L2: OrderedDict[TopicKey, CacheNode] = OrderedDict()
            self.L3: OrderedDict[TopicKey, CacheNode] = OrderedDict()
        else:
            self.L1, self.L2, self.L3 = self._load_cache()
            self.directory = {}
            for od in (self.L1, self.L2, self.L3):
                for key, value in od.items():
                    self.directory[key] = value

    def lookup(self, key: TopicKey) -> Optional[TopicState]:
        """
        Lookup a topic in cache.
        Returns TopicState if found, else None.
        """
        node = self.directory.get(key)
        if node is None:
            return None

        # Update stats
        self._on_access(node)

        # Apply promotion rules
        self._maybe_promote(node)

        return node.state

    def insert_new(self, key: TopicKey, cached_chunk_ids: List[str]) -> TopicState:

        now = time.time()

        state = TopicState(
            key=key,
            cached_chunk_ids=cached_chunk_ids,
            access_count=1,
            last_access_ts=now,
            first_seen_ts=now,
            score=1.0,
            confidence=0.0,
        )

        node = CacheNode(
            key=key,
            state=state,
            level=3,
        )

        if key in self.directory:
            return self.directory[key].state

        self._insert_into_L3(node)
        self.directory[key] = node

        return state

    def _on_access(self, node: CacheNode) -> None:
        """
        Update access stats and recency.
        """
        now = time.time()

        s = node.state
        s.access_count += 1
        s.last_access_ts = now

        s.score = s.access_count + 0.1

        # Update recency ordering in its current level
        if node.level == 1:
            self.L1.move_to_end(node.key)
        elif node.level == 2:
            self.L2.move_to_end(node.key)
        elif node.level == 3:
            self.L3.move_to_end(node.key)

    def _maybe_promote(self, node: CacheNode) -> None:
        """
        Promote node based on thresholds.
        """
        s = node.state

        if node.level == 3 and s.access_count >= self.L3_THRESHOLD:
            self._promote_L3_to_L2(node)

        elif node.level == 2 and s.access_count >= self.L2_THRESHOLD:
            self._promote_L2_to_L1(node)

    def _promote_L3_to_L2(self, node: CacheNode) -> None:
        self.L3.pop(node.key, None)

        node.level = 2
        self.L2[node.key] = node

        if len(self.L2) > self.cap_l2:
            self._demote_L2_to_L3()

    def _promote_L2_to_L1(self, node: CacheNode) -> None:
        self.L2.pop(node.key, None)

        node.level = 1
        self.L1[node.key] = node

        if len(self.L1) > self.cap_l1:
            self._demote_L1_to_L2()

    def _demote_L1_to_L2(self) -> None:
        old_key, old_node = self.L1.popitem(last=False)

        old_node.level = 2
        self.L2[old_key] = old_node

        if len(self.L2) > self.cap_l2:
            self._demote_L2_to_L3()

    def _demote_L2_to_L3(self) -> None:
        old_key, old_node = self.L2.popitem(last=False)

        old_node.level = 3
        self.L3[old_key] = old_node

        if len(self.L3) > self.cap_l3:
            self._evict_from_L3()

    def _insert_into_L3(self, node: CacheNode) -> None:
        self.L3[node.key] = node

        if len(self.L3) > self.cap_l3:
            self._evict_from_L3()

    def _evict_from_L3(self) -> None:
        old_key, old_node = self.L3.popitem(last=False)

        self.directory.pop(old_key, None)

    def _assert_invariants(self):
        all_keys = set(self.L1) | set(self.L2) | set(self.L3)
        assert all_keys == set(self.directory)

    def debug_counts(self):
        self._assert_invariants()
        return {
            "L1": len(self.L1),
            "L2": len(self.L2),
            "L3": len(self.L3),
            "TOTAL": len(self.directory),
        }

    def debug_dump_levels(self):
        def keys(od):
            return list(od.keys())

        self._assert_invariants()
        return {
            "L1": keys(self.L1),
            "L2": keys(self.L2),
            "L3": keys(self.L3),
        }
