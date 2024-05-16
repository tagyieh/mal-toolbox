"""
Command-line interface for MAL toolbox operations

Usage:
    maltoolbox attack-graph generate [options] <model> <lang_file>
    maltoolbox compile <lang_file> <output_file>

Arguments:
    <model>         Path to JSON instance model file.
    <lang_file>     Path to .mar or .mal file containing MAL spec.
    <output_file>   Path to write the JSON result of the compilation.

Options:
    --neo4j         Ingest attack graph and instance model into a Neo4j instance

Notes:
    - <lang_file> can be either a .mar file (generated by the older MAL
      compiler) or a .mal file containing the DSL written in MAL.

    - If --neo4j is used, the Neo4j instance should be running. The connection
      parameters required for this app to reach the Neo4j instance should be
      defined in the default.conf file.
"""
import docopt
import logging
import json
import sys
import zipfile

from . import log_configs, neo4j_configs
from .language import LanguageClassesFactory, LanguageGraph
from .language.compiler import MalCompiler
from .model import Model
from .attackgraph import AttackGraph
from .attackgraph.analyzers.apriori import calculate_viability_and_necessity
from .ingestors import neo4j
from .exceptions import AttackGraphStepExpressionError

logger = logging.getLogger(__name__)


def generate_attack_graph(model_file: str, lang_file: str, send_to_neo4j: bool) -> None:
    try:
        lang_graph = LanguageGraph.from_mar_archive(lang_file)
    except zipfile.BadZipFile:
        lang_graph = LanguageGraph.from_mal_spec(lang_file)

    if log_configs['langspec_file']:
        lang_graph.save_language_specification_to_json(log_configs['langspec_file'])

    lang_classes_factory = LanguageClassesFactory(lang_graph)

    instance_model = Model.load_from_file(model_file, lang_classes_factory)

    if log_configs['model_file']:
        instance_model.save_to_file(log_configs['model_file'])

    try:
        graph = AttackGraph(lang_graph, instance_model)
    except AttackGraphStepExpressionError:
        logger.error('Attack graph generation failed when attempting ' \
            'to resolve attack step expression!')
        sys.exit(1)

    calculate_viability_and_necessity(graph)

    graph.attach_attackers()

    if log_configs['attackgraph_file']:
        graph.save_to_file(
            log_configs['attackgraph_file'])

    if send_to_neo4j:
        logger.debug('Ingest model graph into Neo4J database.')
        neo4j.ingest_model(instance_model,
            neo4j_configs['uri'],
            neo4j_configs['username'],
            neo4j_configs['password'],
            neo4j_configs['dbname'],
            delete=True)
        logger.debug('Ingest attack graph into Neo4J database.')
        neo4j.ingest_attack_graph(graph,
            neo4j_configs['uri'],
            neo4j_configs['username'],
            neo4j_configs['password'],
            neo4j_configs['dbname'],
            delete=False)

def compile(lang_file, output_file):
    compiler = MalCompiler()

    with open(output_file, "w") as f:
        json.dump(compiler.compile(lang_file), f, indent=2)


args = docopt.docopt(__doc__)

if args['attack-graph'] and args['generate']:
    generate_attack_graph(args['<model>'], args['<lang_file>'], args['--neo4j'])
elif args['compile']:
    compile(args['<lang_file>'], args['<output_file>'])
