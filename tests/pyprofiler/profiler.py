import cProfile
import inspect
import pstats
import yaml
import time
import pprint

HISTORY_FILE = "profiling_results.yml"
COMPARE_FILE = "profiling_compare.yml"

class Profiler:
    """Run profiling on functions"""

    def __init__(self, timestamp):
        self.timestamp = round(timestamp)

    def get_function_identifier(self, fun):
        """Append module name with function name to create a unique
        string for each function that is profiled"""
        module_name = fun.__module__
        function_name = fun.__qualname__
        return f"{module_name or ''}:{function_name}"

    def run_profiling(self, fun, *args, store_results=True):
        """Run cProfile for a function with arguments given, print results"""
        function_identifier = self.get_function_identifier(fun)
        print(f"Profiling function {function_identifier}")
        profiler = cProfile.Profile()
        profiler.enable()
        res = fun(*args)
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumtime').print_stats(20)
        if store_results:
            self.store_results(function_identifier, stats)
        return res

    def get_old_results(self) -> dict:
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return dict(yaml.safe_load(f))
        except (FileNotFoundError, TypeError):
            return {}

    def store_results(self, function_name, stats: pstats.Stats) -> None:
        results = self.get_old_results()
        results.setdefault(self.timestamp, {})
        results[self.timestamp][function_name] = stats.total_tt

        with open(HISTORY_FILE, 'w', encoding='utf8') as f:
            yaml.dump(results, f)

    def compare_results(self) -> dict:
        """Compare the results to see improvement in absolute and relative numbers"""

        results = self.get_old_results()
        compared_to_previous = {}
        latest_timestamp = -1
        previous_timestamp = -1

        for timestamp in results.keys():
            if timestamp > latest_timestamp:
                previous_timestamp = latest_timestamp
                latest_timestamp = timestamp
        for fun_signature, duration_latest in results.get(latest_timestamp, {}).items():
            try:
                duration_previous = results.get(previous_timestamp).get(fun_signature)
                diff_s = duration_latest - duration_previous
                diff_percentage = 100 * (duration_latest - duration_previous) / duration_previous

                compared_to_previous[fun_signature] = {}

                diff_s_string = f"{'+' if diff_s > 0 else ''}{round(diff_s, 4)}s"
                compared_to_previous[fun_signature]['diff_s'] = diff_s_string

                diff_percentage_string = f"{'+' if diff_percentage > 0 else ''}{round(diff_percentage)}%"
                compared_to_previous[fun_signature]['diff_percentage'] = diff_percentage_string

            except Exception:
                # If one of the timestamps did not have the function
                continue
        
        with open(COMPARE_FILE, 'w', encoding='utf8') as f:
            yaml.dump(compared_to_previous, f)


