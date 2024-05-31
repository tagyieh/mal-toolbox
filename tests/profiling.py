"""Profiling for maltoolbox"""

import json
import os
import sys
import time
import yaml

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
from pyprofiler.profiler import Profiler

from conftest import path_testdata
from test_model import create_application_asset


def generate_model(lang_classes_factory, n_assets):
    """Generate a model with n assets"""
    model = Model("Test Model", lang_classes_factory)
    for i in range(n_assets):
        asset = create_application_asset(model, f'Application {i}')
        model.add_asset(asset)
    return model

class ProfileMALToolbox(Profiler):
    def profile_yaml_load(self):
        """Yaml load"""
        file_path = path_testdata("model_1000.yml")
        self.run_profiling(yaml.unsafe_load, open(file_path))
        self.run_profiling(yaml.safe_load, open(file_path))

    def profile_json_load(self):
        """json.load"""
        file_path = path_testdata("model_1000.json")
        self.run_profiling(json.load, open(file_path))

    def profile_language_graph_load_from_file(self):
        """LanguageGraph.load_from_file"""
        file_path = path_testdata('org.mal-lang.coreLang-1.0.0.mar')
        self.run_profiling(LanguageGraph.from_mar_archive, file_path)

    def profile_model_load_from_file(self):
        """Model.load_from_file"""
        file_path = path_testdata("org.mal-lang.coreLang-1.0.0.mar")
        model_file_path = path_testdata("model_1000.json")

        language_graph = LanguageGraph.from_mar_archive(file_path)
        lang_classes_factory = LanguageClassesFactory(language_graph)
        self.run_profiling(
            Model.load_from_file, model_file_path, lang_classes_factory
        )

    def profile_attackgraph_init(self):
        """AttackGraph()"""
        file_path = path_testdata("org.mal-lang.coreLang-1.0.0.mar")
        language_graph = LanguageGraph.from_mar_archive(file_path)
        lang_classes_factory = LanguageClassesFactory(language_graph)
        model = generate_model(lang_classes_factory, 1000)
        self.run_profiling(AttackGraph, language_graph, model)

    def profile_create_attack_graph_wrapper(self):
        """Profile the create_attack_graph wrapper"""
        lang_file = path_testdata('org.mal-lang.coreLang-1.0.0.mar')
        model_file = path_testdata("model_1000.yml")
        self.run_profiling(create_attack_graph, lang_file, model_file)

    def profile_attack_graph_generate_graph(self):
        """Profile the _generate_graph wrapper"""
        file_path = path_testdata("org.mal-lang.coreLang-1.0.0.mar")
        language_graph = LanguageGraph.from_mar_archive(file_path)
        lang_classes_factory = LanguageClassesFactory(language_graph)
        model = generate_model(lang_classes_factory, 1000)
        attack_graph = AttackGraph(language_graph, model)

        self.run_profiling(attack_graph._generate_graph)


if __name__ == "__main__":
    timestamp = time.time()
    profiler = ProfileMALToolbox(timestamp)
    for method_name in dir(profiler):
        if callable(getattr(profiler, method_name))\
           and method_name.startswith('profile_'):
            method = getattr(profiler, method_name)
            method()
    profiler.compare_results()
