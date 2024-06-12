"""
MAL-Toolbox Attack Graph Module
"""

import logging
import json

from typing import Optional, List

from maltoolbox.file_utils import (
    load_dict_from_json_file, load_dict_from_yaml_file,
    save_dict_to_file
)

from .node import AttackGraphNode
from .attacker import Attacker
from ..exceptions import AttackGraphStepExpressionError
from ..language import specification, LanguageGraph
from ..model import Model


logger = logging.getLogger(__name__)

# TODO see if (part of) this can be incorporated into the LanguageGraph, so that
# the LanguageGraph's _lang_spec private property does not need to be accessed
def _process_step_expression(lang_graph: LanguageGraph, model: Model,
    target_assets: list, step_expression: dict):
    """
    Recursively process an attack step expression.

    Arguments:
    lang            - a dictionary representing the MAL language specification
    model           - a maltoolbox.model.Model instance from which the attack
                      graph was generated
    target_assets   - the list of assets that this step expression should apply
                      to. Initially it will contain the asset to which the
                      attack step belongs
    step_expression - a dictionary containing the step expression

    Return:
    A tuple pair containing a list of all of the target assets and the name of
    the attack step.
    """

    if logger.isEnabledFor(logging.DEBUG):
        # Avoid running json.dumps when not in debug
        logger.debug('Processing Step Expression:\n' \
            + json.dumps(step_expression, indent = 2))

    match (step_expression['type']):
        case 'attackStep':
            # The attack step expression just adds the name of the attack
            # step. All other step expressions only modify the target assets.
            return (target_assets, step_expression['name'])

        case 'union' | 'intersection' | 'difference':
            # The set operators are used to combine the left hand and right
            # hand targets accordingly.
            lh_targets, lh_attack_steps = _process_step_expression(
                lang_graph, model, target_assets, step_expression['lhs'])
            rh_targets, rh_attack_steps = _process_step_expression(
                lang_graph, model, target_assets, step_expression['rhs'])

            new_target_assets = []
            match (step_expression['type']):
                case 'union':
                    new_target_assets = lh_targets
                    for ag_node in rh_targets:
                        if next((lnode for lnode in new_target_assets \
                            if lnode.id != ag_node.id), None):
                            new_target_assets.append(ag_node)

                case 'intersection':
                    for ag_node in rh_targets:
                        if next((lnode for lnode in lh_targets \
                            if lnode.id == ag_node.id), None):
                            new_target_assets.append(ag_node)

                case 'difference':
                    new_target_assets = lh_targets
                    for ag_node in lh_targets:
                        if next((rnode for rnode in rh_targets \
                            if rnode.id != ag_node.id), None):
                            new_target_assets.remove(ag_node)

            return (new_target_assets, None)

        case 'variable':
            # Fetch the step expression associated with the variable from
            # the language specification and resolve that.
            for target_asset in target_assets:
                if (hasattr(target_asset, 'type')):
                    # TODO how can this info be accessed in the lang_graph
                    # directly without going through the private method?
                    variable_step_expr = lang_graph._get_variable_for_asset_type_by_name(
                        target_asset.type, step_expression['name'])
                    return _process_step_expression(
                        lang_graph, model, target_assets, variable_step_expr)

                else:
                    logger.error('Requested variable from non-asset'
                        f'target node: {target_asset} which cannot be'
                        'resolved.')
            return ([], None)

        case 'field':
            # Change the target assets from the current ones to the associated
            # assets given the specified field name.
            new_target_assets = []
            for target_asset in target_assets:
                new_target_assets.extend(model.\
                    get_associated_assets_by_field_name(target_asset,
                        step_expression['name']))
            return (new_target_assets, None)

        case 'transitive':
            # The transitive expression is very similar to the field
            # expression, but it proceeds recursively until no target is
            # found and it and it sets the new targets to the entire list
            # of assets identified during the entire transitive recursion.
            new_target_assets = []
            for target_asset in target_assets:
                new_target_assets.extend(model.\
                    get_associated_assets_by_field_name(target_asset,
                        step_expression['stepExpression']['name']))
            if new_target_assets:
                (additional_assets, _) = _process_step_expression(
                    lang_graph, model, new_target_assets, step_expression)
                new_target_assets.extend(additional_assets)
                return (new_target_assets, None)
            else:
                return ([], None)

        case 'subType':
            new_target_assets = []
            for target_asset in target_assets:
                (assets, _) = _process_step_expression(
                    lang_graph, model, target_assets,
                    step_expression['stepExpression'])
                new_target_assets.extend(assets)

            selected_new_target_assets = (asset for asset in \
                new_target_assets if specification.extends_asset(
                    lang_graph,
                    asset.type,
                    step_expression['subType']))
            return (selected_new_target_assets, None)

        case 'collect':
            # Apply the right hand step expression to left hand step
            # expression target assets.
            lh_targets, _ = _process_step_expression(
                lang_graph, model, target_assets, step_expression['lhs'])
            return _process_step_expression(lang_graph, model, lh_targets,
                step_expression['rhs'])


        case _:
            logger.error('Unknown attack step type: '
                f'{step_expression["type"]}')
            return ([], None)

class AttackGraph():
    """Graph representation of attack steps"""
    def __init__(self, lang_graph = None, model: Optional[Model] = None):
        self.nodes = []
        self.id_to_node = {}  # to get nodes by id faster
        self.full_name_to_node = {}  # to get nodes by full name faster
        self.attackers = []
        self.id_to_attacker = {}  # to get attackers by id faster

        self.model = model
        self.lang_graph = lang_graph
        self.next_node_id = 0
        self.next_attacker_id = 0
        if self.model is not None and self.lang_graph is not None:
            self._generate_graph()

    def __repr__(self) -> str:
        return f'AttackGraph({len(self.nodes)} nodes)'

    def _to_dict(self):
        """Convert AttackGraph to list"""
        serialized_attack_steps = []
        serialized_attackers = []
        for ag_node in self.nodes:
            serialized_attack_steps.append(ag_node.to_dict())
        for attacker in self.attackers:
            serialized_attackers.append(attacker.to_dict())
        return {
            'attack_steps': serialized_attack_steps,
            'attackers': serialized_attackers,
        }

    def save_to_file(self, filename):
        """Save to json/yml depending on extension"""
        return save_dict_to_file(filename, self._to_dict())

    @classmethod
    def _from_dict(cls, serialized_object, model=None):
        """Create AttackGraph from dict
        Args:
        serialized_object   - AttackGraph in dict format
        model               - Optional Model to add connections to
        """

        attack_graph = AttackGraph()
        serialized_attack_steps = serialized_object['attack_steps']
        serialized_attackers = serialized_object['attackers']

        # Create all of the nodes in the imported attack graph.
        for node_dict in serialized_attack_steps:
            ag_node = AttackGraphNode(
                type=node_dict['type'],
                name=node_dict['name'],
                ttc=node_dict['ttc']
            )

            ag_node.defense_status = float(node_dict['defense_status']) if \
                'defense_status' in node_dict else None
            ag_node.existence_status = node_dict['existence_status'] \
                == 'True' if 'existence_status' in node_dict else None
            ag_node.is_viable = node_dict['is_viable'] == 'True' if \
                'is_viable' in node_dict else True
            ag_node.is_necessary = node_dict['is_necessary'] == 'True' if \
                'is_necessary' in node_dict else True
            ag_node.mitre_info = str(node_dict['mitre_info']) if \
                'mitre_info' in node_dict else None
            ag_node.tags = node_dict['tags'] if \
                'tags' in node_dict else []

            attack_graph.add_node(ag_node)

        # Re-establish links between nodes.
        for node_dict in serialized_attack_steps:
            _ag_node = attack_graph.get_node_by_id(node_dict['id'])
            if not isinstance(_ag_node, AttackGraphNode):
                logger.error(
                    f'Failed to find node with id {node_dict["id"]}'
                    f' when loading from attack graph from dict'
                )
            else:
                for child_id in node_dict['children']:
                    child = attack_graph.get_node_by_id(child_id)
                    if child is None:
                        logger.error(
                            f'Failed to find child node with id {child_id}'
                            f' when loading from attack graph from dict'
                        )
                        return None
                    _ag_node.children.append(child)

                for parent_id in node_dict['parents']:
                    parent = attack_graph.get_node_by_id(parent_id)
                    if parent is None:
                        logger.error(
                            f'Failed to find parent node with id {parent_id} '
                            'when loading from attack graph from dict'
                        )
                        return None
                    _ag_node.parents.append(parent)

                # Also recreate asset links if model is available.
                if model and 'asset' in node_dict:
                    asset = model.get_asset_by_name(
                        node_dict['asset'])
                    if asset is None:
                        logger.error(
                            f'Failed to find asset with id {node_dict["asset"]}'
                            'when loading from attack graph dict'
                        )
                        return None
                    _ag_node.asset = asset
                    if hasattr(asset, 'attack_step_nodes'):
                        attack_step_nodes = list(asset.attack_step_nodes)
                        attack_step_nodes.append(_ag_node)
                        asset.attack_step_nodes = attack_step_nodes
                    else:
                        asset.attack_step_nodes = [_ag_node]

        for attacker in serialized_attackers:
            ag_attacker = Attacker(
                name = attacker['name'],
                entry_points = [],
                reached_attack_steps = []
            )
            attack_graph.add_attacker(
                name = ag_attacker,
                id = int(attacker['id']),
                entry_points = attacker['entry_points'],
                reached_attack_steps = attacker['reached_attack_steps']
            )

        return attack_graph

    @classmethod
    def load_from_file(cls, filename, model=None):
        """Create from json or yaml file depending on file extension"""
        serialized_model = None
        if filename.endswith(('.yml', '.yaml')):
            serialized_model = load_dict_from_yaml_file(filename)
        elif filename.endswith('.json'):
            serialized_model = load_dict_from_json_file(filename)
        else:
            raise ValueError('Unknown file extension, expected json/yml/yaml')
        return cls._from_dict(serialized_model, model=model)

    def get_node_by_id(self, node_id: int) -> Optional[AttackGraphNode]:
        """
        Return the attack node that matches the id provided.

        Arguments:
        node_id     - the id of the attack graph node we are looking for

        Return:
        The attack step node that matches the given id.
        """

        logger.debug(f'Looking up node with id {node_id}')
        return self.id_to_node.get(node_id)

    def get_node_by_full_name(self, full_name: str) -> Optional[AttackGraphNode]:
        """
        Return the attack node that matches the full name provided.

        Arguments:
        full_name   - the full name of the attack graph node we are looking
                      for

        Return:
        The attack step node that matches the given full name.
        """

        logger.debug(f'Looking up node with id {full_name}')
        return self.full_name_to_node.get(full_name)

    def get_attacker_by_id(self, attacker_id: int) -> Optional[Attacker]:
        """
        Return the attacker that matches the id provided.

        Arguments:
        attacker_id     - the id of the attacker we are looking for

        Return:
        The attacker that matches the given id.
        """

        logger.debug(f'Looking up attacker with id {attacker_id}')
        return self.id_to_attacker.get(attacker_id)

    def attach_attackers(self):
        """
        Create attackers and their entry point nodes and attach them to the
        relevant attack step nodes and to the attackers.
        """

        logger.info(
            f'Attach attackers from "{self.model.name}" model to the graph.'
        )
        for attacker_info in self.model.attackers:
            attacker = Attacker(
                name = attacker_info.name,
                entry_points = [],
                reached_attack_steps = []
            )
            self.add_attacker(attacker)

            for (asset, attack_steps) in attacker_info.entry_points:
                for attack_step in attack_steps:
                    full_name = asset.name + ':' + attack_step
                    ag_node = self.get_node_by_full_name(full_name)
                    if not ag_node:
                        logger.warning(
                            'Failed to find attacker entry point '
                            f'{attack_step_id} for {attacker.name}.'
                        )
                        continue
                    attacker.compromise(ag_node)

            attacker.entry_points = attacker.reached_attack_steps

    def _generate_graph(self):
        """
        Generate the attack graph based on the original model instance and the
        MAL language specification provided at initialization.
        """

        # First, generate all of the nodes of the attack graph.
        for asset in self.model.assets:

            logger.debug(
                f'Generating attack steps for asset {asset.name} '
                f'which is of class {asset.type}.'
            )

            attack_step_nodes = []

            # TODO probably part of what happens here is already done in lang_graph
            attack_steps = self.lang_graph._get_attacks_for_asset_type(asset.type)

            for attack_step_name, attack_step_attribs in attack_steps.items():
                logger.debug(
                    f'Generating attack step node for {attack_step_name}.'
                )

                defense_status = None
                existence_status: Optional[bool] = None
                node_id = asset.name + ':' + attack_step_name

                match (attack_step_attribs['type']):
                    case 'defense':
                        # Set the defense status for defenses
                        defense_status = getattr(asset, attack_step_name)
                        logger.debug('Setting the defense status of '\
                            f'{node_id} to {defense_status}.')

                    case 'exist' | 'notExist':
                        # Resolve step expression associated with (non-)existence
                        # attack steps.
                        (target_assets, attack_step) = _process_step_expression(
                            self.lang_graph,
                            self.model,
                            [asset],
                            attack_step_attribs['requires']['stepExpressions'][0])
                        # If the step expression resolution yielded the target
                        # assets then the required assets exist in the model.
                        existence_status = target_assets != []

                mitre_info = attack_step_attribs['meta']['mitre'] if 'mitre' in\
                    attack_step_attribs['meta'] else None
                ag_node = AttackGraphNode(
                    type = attack_step_attribs['type'],
                    asset = asset,
                    name = attack_step_name,
                    ttc = attack_step_attribs['ttc'],
                    children = [],
                    parents = [],
                    defense_status = defense_status,
                    existence_status = existence_status,
                    is_viable = True,
                    is_necessary = True,
                    mitre_info = mitre_info,
                    tags = attack_step_attribs['tags'],
                    compromised_by = []
                )
                ag_node.attributes = attack_step_attribs
                attack_step_nodes.append(ag_node)
                self.add_node(ag_node)
            asset.attack_step_nodes = attack_step_nodes

        # Then, link all of the nodes according to their associations.
        for ag_node in self.nodes:
            logger.debug('Determining children for attack step '\
                f'{ag_node.id}.')
            step_expressions = \
                ag_node.attributes['reaches']['stepExpressions'] if \
                    isinstance(ag_node.attributes, dict) and ag_node.attributes['reaches'] else []

            for step_expression in step_expressions:
                # Resolve each of the attack step expressions listed for this
                # attack step to determine children.
                (target_assets, attack_step) = _process_step_expression(
                    self.lang_graph,
                    self.model,
                    [ag_node.asset],
                    step_expression)

                for target in target_assets:
                    target_node_full_name = target.name + ':' + attack_step
                    target_node = self.get_node_by_full_name(
                        target_node_full_name
                    )
                    if not target_node:
                        msg = 'Failed to find target node ' \
                        f'{target_node_id} to link with for attack step ' \
                        f'{ag_node.id}!'
                        logger.error(msg)
                        raise AttackGraphStepExpressionError(msg)
                    ag_node.children.append(target_node)
                    target_node.parents.append(ag_node)

    def regenerate_graph(self):
        """
        Regenerate the attack graph based on the original model instance and
        the MAL language specification provided at initialization.
        """

        self.nodes = []
        self.attackers = []
        self._generate_graph()

    def add_node(
            self,
            node: AttackGraphNode,
            node_id: int = None
        ):
        """Add a node to the graph
        Arguments:
        node    - the node to add
        node_id - the id to assign to this node, usually used when loading
                  an attack graph from a file
        """
        self.nodes.append(node)
        node.id = node_id or self.next_node_id
        if node.id in self.id_to_node:
            raise ValueError(f'Node index {node_id} already in use.')

        self.next_node_id = max(node.id + 1, self.next_node_id)
        self.id_to_node[node.id] = node
        self.full_name_to_node[node.get_full_name()] = node

    def remove_node(self, node):
        """Remove node from attack graph
        Arguments:
        node    - the node we wish to remove from the attack graph
        """
        for child in node.children:
            child.parents.remove(node)
        for parent in node.parents:
            parent.children.remove(node)
        self.nodes.remove(node)
        del self.id_to_node[node.id]
        del self.full_name_to_node[node.get_full_name()]

    def add_attacker(
            self,
            attacker: Attacker,
            attacker_id: int = None,
            entry_points: List[int] = [],
            reached_attack_steps: List[int] = []
        ):
        """Add an attacker to the graph
        Arguments:
        attacker                - the attacker to add
        attacker_id             - the id to assign to this attacker, usually
                                  used when loading an attack graph from a
                                  file
        entry_points            - list of attack step ids that serve as entry
                                  points for the attacker
        reached_attack_steps    - list of ids of the attack steps that the
                                  attacker has reached
        """
        attacker.id = attacker_id or self.next_attacker_id
        if attacker.id in self.id_to_attacker:
            raise ValueError(f'Attacker index {attacker_id} already in use.')

        self.next_attacker_id = max(attacker.id + 1, self.next_attacker_id)
        for node_id in reached_attack_steps:
            node = self.get_node_by_id(node_id)
            attacker.compromise(node)
        for node_id in entry_points:
            node = self.get_node_by_id(node_id)
            attacker.entry_points.append(node)
        self.attackers.append(attacker)
        self.id_to_attacker[attacker.id] = attacker

    def remove_attacker(self, attacker: Attacker):
        """Remove attacker from attack graph
        Arguments:
        attacker    - the attacker we wish to remove from the attack graph
        """
        for node in attacker.reached_attack_steps:
            attacker.undo_compromise(node)
        self.attackers.remove(attacker)
        del self.id_to_attacker[attacker.id]
