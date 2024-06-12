"""
MAL-Toolbox Attack Graph Node Dataclass
"""

from dataclasses import field, dataclass
from typing import Any, Optional

from . import Attacker

@dataclass
class AttackGraphNode:
    type: str
    name: str
    ttc: dict = None
    id: int = None
    asset: Any = None
    children: list['AttackGraphNode'] = field(default_factory=list)
    parents: list['AttackGraphNode'] = field(default_factory=list)
    defense_status: Optional[float] = None
    existence_status: Optional[bool] = None
    is_viable: bool = True
    is_necessary: bool = True
    compromised_by: list['Attacker'] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    mitre_info: Optional[str] = None
    attributes: Optional[dict] = None

    # Optional extra metadata for AttackGraphNode
    extras: Optional[dict] = None

    def to_dict(self):
        node_dict = {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'ttc': self.ttc,
            'children': [child.get_full_name() for child in self.children],
            'parents': [parent.get_full_name() for parent in self.parents],
            'compromised_by': [ attacker.name for attacker in \
                self.compromised_by]
        }

        if self.asset is not None:
            node_dict['asset'] = str(self.asset.name)
        if self.defense_status is not None:
            node_dict['defense_status'] = str(self.defense_status)
        if self.existence_status is not None:
            node_dict['existence_status'] = str(self.existence_status)
        if self.is_viable is not None:
            node_dict['is_viable'] = str(self.is_viable)
        if self.is_necessary is not None:
            node_dict['is_necessary'] = str(self.is_necessary)
        if self.mitre_info is not None:
            node_dict['mitre_info'] = str(self.mitre_info)
        if self.tags:
            node_dict['tags'] = str(self.tags)
        if self.extras:
            node_dict['extra'] = self.extras

        return node_dict

    def __repr__(self):
        return str(self.to_dict())

    def is_compromised(self):
        """
        Return True if any attackers have compromised this node.
        False, otherwise.
        """
        return len(self.compromised_by) > 0

    def is_compromised_by(self, attacker):
        """
        Return True if the attacker given as an argument has compromised this
        node.
        False, otherwise.

        Arguments:
        attacker    - the attacker we are interested in
        """
        return attacker in self.compromised_by

    def compromise(self, attacker):
        """
        Have the attacker given as a parameter compromise this node.

        Arguments:
        attacker    - the attacker that will compromise the node
        """
        attacker.compromise(self)

    def undo_compromise(self, attacker):
        """
        Remove the attacker given as a parameter from the list of attackers
        that have compromised this node.

        Arguments:
        attacker    - the attacker that we wish to remove from the compromised
                      list.
        """
        attacker.undo_compromise(self)

    def is_enabled_defense(self):
        """
        Return True if this node is a defense node and it is enabled and not
        suppressed via tags.
        False, otherwise.
        """
        return self.type == 'defense' and \
            'suppress' not in self.tags and \
            self.defense_status == 1.0

    def is_available_defense(self):
        """
        Return True if this node is a defense node and it is not fully enabled
        and not suppressed via tags.
        False, otherwise.
        """
        return self.type == 'defense' and \
            'suppress' not in self.tags and \
            self.defense_status != 1.0

    def get_full_name(self) -> str:
        """
        Return the full name of the attack step. This is a combination of the
        asset name to which the attack step belongs and attack step name
        itself.
        """
        if self.asset:
            full_name = self.asset.name + ':' + self.name
        else:
            full_name = str(self.id) + ':' + self.name
        return full_name
