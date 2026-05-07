# Imports
from pprint import pprint
from IPython import get_ipython
from watertap.core.solvers import get_solver
from parameter_sweep import ParameterSweep
from wrd.surrogate_models.param_sweep_fxs import (
    optimize,
    build_flowsheet,
    build_sweep_params,
    build_outputs,
    initialize_model,
)


def create_parameter_sweep_object(num_samples, num_procs, op_limits, var_lims):
    solver = get_solver()
    kwargs_dict = {
        # Arguments being used in the demo
        "h5_results_file_name": "ps_demo.h5",  # Resulting output file name
        "build_model": build_flowsheet,  # Function that builds the flowsheet model
        "build_model_kwargs": dict(scenario=None, op_limts=op_limits),
        "build_sweep_params": build_sweep_params,  # Function for building sweep param dictionary
        "build_sweep_params_kwargs": dict(
            num_samples=num_samples, var_lims=var_lims, scenario="default"
        ),
        "build_outputs": build_outputs,  # Function the builds outputs to save
        "build_outputs_kwargs": {},
        "optimize_function": optimize,  # Optimize flow sheet function
        "optimize_kwargs": {"solver": solver, "check_termination": False},
        "initialize_function": initialize_model,
        "initialize_kwargs": {},
        "parallel_back_end": "MultiProcessing",  # ConcurrentFutures, MPI, Ray available
        "number_of_subprocesses": num_procs,
        # Additional useful keyword arguments
        "csv_results_file_name": None,  # For storing results as CSV
        "h5_parent_group_name": None,  # Useful for loop tool
        "update_sweep_params_before_init": False,
        "initialize_before_sweep": False,
        "reinitialize_function": None,
        "reinitialize_kwargs": {},
        "reinitialize_before_sweep": False,
        "probe_function": None,
        # Post-processing arguments
        "interpolate_nan_outputs": False,
        # Advanced Users
        "debugging_data_dir": None,
        "log_model_states": False,
        "custom_do_param_sweep": None,  # Advanced users only!
        "custom_do_param_sweep_kwargs": {},
    }
    ps = ParameterSweep(**kwargs_dict)
    return ps, kwargs_dict

if __name__ == "__main__":
    num_samples = 2
    num_procs = 2
    op_limts = {
        "Stage 1": {
            "RR_min": 0.55,
            "RR_max": 0.62,
            "Qin_min": 420 / 3600,
            "Qin_max": 635 / 3600,
        },
        "Stage 2": {
            "RR_min": 0.55,
            "RR_max": 0.62,
            "Qin_min": 200 / 3600,
            "Qin_max": 251 / 3600,
        },
        "Stage 3": {
            "RR_min": 0.40,
            "RR_max": 0.55,
            "Qin_min": 75 / 3600,
            "Qin_max": 126 / 3600,
        },
    }
    var_lims = {
        "RR_lb": 0.88,
        "RR_ub": 0.93,
        "Qin_lb": 420 / 3600,  # m3/s
        "Qin_ub": 635 / 3600,  # m3/s
    }
    ps, kwargs_dict = create_parameter_sweep_object(
        num_samples, num_procs, op_limts, var_lims
    )

    results_array, results_dict = ps.parameter_sweep(
        kwargs_dict["build_model"],
        kwargs_dict["build_sweep_params"],
        build_outputs=kwargs_dict["build_outputs"],
        build_outputs_kwargs=kwargs_dict["build_outputs_kwargs"],
        num_samples=num_samples,
        seed=None,
        build_model_kwargs=kwargs_dict["build_model_kwargs"],
        build_sweep_params_kwargs=kwargs_dict["build_sweep_params_kwargs"],
    )

    # Display and save results
    pprint(results_dict)
    pprint(results_array)
