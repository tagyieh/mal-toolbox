import argparse
from pyprofiler.profiler import PyProfiler

def cli():
    """CLI for PyProfiler - the easy profiler"""
    parser = argparse.ArgumentParser(
        description=(
            "PyProfiler - a profiling command line tool for python packages."
            "Can be used to run PyProfile files and compare profiling runs."
        )
    )

    subparsers = parser.add_subparsers(
        dest='action', required=True, help='Action to perform'
    )

    # Subparser for the 'compare' action
    parser_compare = subparsers.add_parser(
        'compare', help='Compare two profile runs between each other'
    )
    parser_compare.add_argument(
        'profile_run_name_before', type=str,
        help='The name of the `before` profile run'
    )
    parser_compare.add_argument(
        'profile_run_name_after', type=str,
        help='The name of the `after` profile run'
    )

    # Subparser for the 'profile' action
    parser_profile = subparsers.add_parser(
        'profile', help='Run PyProfiling on a pyprofiling file'
    )
    parser_profile.add_argument(
        '-n', '--name_of_run',
        type=str, help='Name of this profiling run'
    )
    parser_profile.add_argument(
        '-v', '--verbose',
        help="Show more info like stack strace for profiling",
        action='store_true'
    )
    parser_profile.add_argument(
        'pyprofile_file', type=str,
        help=(
            'Filename of pyprofile file to run profiling on'
            '(must contain at least one class that inherits from PyProfile)'
        )
    )
    args = parser.parse_args()

    if args.action == "profile":
        PyProfiler.create_profiler(
            args.pyprofile_file,
            requested_run_name=args.name_of_run,
            verbose=args.verbose
        )

    elif args.action == "compare":
        PyProfiler.compare_results(
            args.profile_run_name_before,
            args.profile_run_name_after
        )
    else:
        raise RuntimeError(f"Unknown action {args.action}")

if __name__ == "__main__":
    cli()
