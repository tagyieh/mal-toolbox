"""Classes used in PyProfiler"""

from __future__ import annotations

import cProfile
from datetime import datetime
import pstats
import time
import timeit

import yaml

from pyprofiler.utils import load_classes_from_file
from pyprofiler.printer import Printer, Color

HISTORY_FILE = "profiling_results.yml"
COMPARE_FILE = "profiling_compare.yml"


class PyProfiler:
    """Run profiling on functions"""
    printer = Printer()

    def __init__(self, name=None, verbose=False):
        self.timestamp = round(time.time())
        self.name = name or datetime.strftime(datetime.now(), "%Y-%m-%d-%H:%M:%S")
        self.verbose = verbose
        print(f"Created PyProfiler with name {self.name}.")


    def get_function_identifier(self, fun):
        """Append module name with function name to create a unique
        string for each function that is profiled"""
        module_name = fun.__module__
        function_name = fun.__qualname__
        return f"{module_name or ''}:{function_name}"

    def pyprofile(
            self, fun, *args,
            store_results=True,
            num_repeated=1000
        ):
        """Run cProfile for a function with arguments given, print results"""
        function_identifier = self.get_function_identifier(fun)
        self.printer.print(f"Profiling function {function_identifier}")

        time_taken = timeit.Timer(
            lambda: fun(*args)
        ).timeit(number=num_repeated)
        self.printer.print(
            f"\t Total time (repeated {num_repeated}) was "
            f"{round(time_taken, 4)}s"
        )

        # Run cProfile to see stack trace
        if self.verbose:
            profiler = cProfile.Profile()
            profiler.enable()
            fun(*args)
            profiler.disable()
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumtime').print_stats(10)

        if store_results:
            self.store_results(function_identifier, time_taken / num_repeated)

    @classmethod
    def create_profiler(
        cls, pyprofiler_file, requested_run_name=None, verbose=False):
        """Create and run profiling with a PyProfiler file"""

        classes = load_classes_from_file(pyprofiler_file, cls.__name__)

        old_results = cls.get_old_results()

        run_name = requested_run_name
        if run_name:
            appended_int = 2
            while run_name in old_results:
                run_name = f"{requested_run_name}{appended_int}"
                appended_int += 1

        for pyprofiler_class in classes:
            profiler = pyprofiler_class(run_name, verbose=verbose)
            for method_name in dir(profiler):
                if callable(getattr(profiler, method_name))\
                and method_name.startswith('profile_'):
                    method = getattr(profiler, method_name)
                    method()

            # Compare previous and current latest run
            run_name_before, run_name_after = profiler.get_two_latest_runs()
            profiler.compare_results(run_name_before, run_name_after)

    @classmethod
    def get_old_results(cls) -> dict:
        """Get results from previous profiling runs"""
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return dict(yaml.safe_load(f))
        except (FileNotFoundError, TypeError):
            return {}

    def store_results(self, function_name, time_taken_avg) -> None:
        """Store the results from the profiling run"""
        results = self.get_old_results()
        results.setdefault(self.name, {})
        results[self.name]["timestamp"] = self.timestamp
        results[self.name].setdefault("functions", {})
        results[self.name]["functions"][function_name] = time_taken_avg

        with open(HISTORY_FILE, 'w', encoding='utf8') as f:
            yaml.dump(results, f)

    def get_two_latest_runs(self):
        """Find the two latest ran profile names"""
        latest_run = {}
        latest_run_name = ""
        previous_latest_run = {}
        previous_latest_run_name = ""

        profile_runs = self.get_old_results()
        for run_name, run in profile_runs.items():
            if run.get('timestamp') > latest_run.get("timestamp", -1):
                previous_latest_run = latest_run
                previous_latest_run_name = latest_run_name
                latest_run = run
                latest_run_name = run_name
            elif run.get('timestamp') > previous_latest_run.get("timestamp", -1):
                previous_latest_run = run
                previous_latest_run_name = run_name

        return previous_latest_run_name, latest_run_name

    @classmethod
    def format_time_diff_percentage(cls, diff_perc):
        """Set color for the command line text"""
        color = Color.OFF
        if diff_perc < -5:
            color = Color.GREEN
        elif diff_perc > 5:
            color = Color.RED

        diff_perc_string = f"{'+' if diff_perc > 0 else ''}{diff_perc}%"
        return cls.printer.text_in_color(diff_perc_string, color)

    @classmethod
    def compare_results(
        cls, profile_run_name_before, profile_run_name_after) -> dict:
        """Compare results to see improvement between two profiling runs"""

        profile_runs = cls.get_old_results()
        results = {"functions": {}}

        results["from"] = profile_run_name_before
        results["to"] = profile_run_name_after

        profile_run_before = profile_runs.get(
            profile_run_name_before, {}).get("functions", {})
        profile_run_after = profile_runs.get(
            profile_run_name_after, {}).get("functions", {})

        if not profile_run_before or not profile_run_after:
            cls.printer.print(
                "Can not compare since there were no results to compare with"
            )
            return

        for fun_signature, duration_after in profile_run_after.items():
            try:
                duration_before = profile_run_before.get(fun_signature)
                diff_s = duration_after - duration_before
                diff_perc = (
                    100 * (duration_after - duration_before) / duration_before
                )
                results["functions"][fun_signature] = {}

                diff_s_string = f"{'+' if diff_s > 0 else ''}{round(diff_s, 4)}s"
                results["functions"][fun_signature]['diff_s'] = diff_s_string

                diff_perc_str = cls.format_time_diff_percentage(round(diff_perc, 2))
                results["functions"][fun_signature]['diff_percentage'] = diff_perc_str

            except TypeError:
                # If one of the timestamps did not have the function
                print(f"Failed to find function {fun_signature} in previous run")
                continue

        print("================================================================")
        print(f"DIFF FROM {profile_run_name_before} TO {profile_run_name_after}")
        for func_signature, diffs in results["functions"].items():
            print(f"{func_signature}: {diffs['diff_percentage']}")
