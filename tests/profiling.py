"""Profiling for maltoolbox"""

import os
import sys

# Add maltoolbox package to python path
# so we profile the local version
package_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)
sys.path.insert(0, package_path)

from maltoolbox.model import Model
from maltoolbox.language import LanguageGraph, LanguageClassesFactory
from maltoolbox.attackgraph import AttackGraph
from maltoolbox.wrappers import create_attack_graph
from tests.pyprofiler.profiler import PyProfiler

from conftest import path_testdata
from test_model import create_application_asset


def generate_model(lang_classes_factory, n_assets):
    """Generate a model with n assets"""
    model = Model("Test Model", lang_classes_factory)
    for i in range(n_assets):
        asset = create_application_asset(model, f'Application {i}')
        model.add_asset(asset)
    return model

class ProfileMALToolbox(PyProfiler):
    """Profiling for MAL Toolbox using PyProfiler"""

    def profile_attackgraph_init(self):
        """AttackGraph()"""
        file_path = path_testdata("org.mal-lang.coreLang-1.0.0.mar")
        language_graph = LanguageGraph.from_mar_archive(file_path)
        lang_classes_factory = LanguageClassesFactory(language_graph)
        model = generate_model(lang_classes_factory, 5)
        self.pyprofile(AttackGraph, language_graph, model, num_repeated=10)

    def profile_create_attack_graph_wrapper(self):
        """Profile the create_attack_graph wrapper"""
        lang_file = path_testdata('org.mal-lang.coreLang-1.0.0.mar')
        model_file = path_testdata("simple_example_model.yml")
        self.pyprofile(
            create_attack_graph, lang_file, model_file, num_repeated=10
        )

    def profile_attack_graph_generate_graph(self):
        """Profile the _generate_graph wrapper"""
        file_path = path_testdata("org.mal-lang.coreLang-1.0.0.mar")
        language_graph = LanguageGraph.from_mar_archive(file_path)
        lang_classes_factory = LanguageClassesFactory(language_graph)
        model = generate_model(lang_classes_factory, 5)
        attack_graph = AttackGraph(language_graph, model)

        self.pyprofile(attack_graph._generate_graph, num_repeated=10)

    def profile_languagegraph_create(self):
        """Profile the language Graph"""
        file_path = path_testdata("org.mal-lang.coreLang-1.0.0.mar")
        self.pyprofile(
            LanguageGraph.from_mar_archive, file_path, num_repeated=10)
