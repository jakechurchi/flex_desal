import pandas as pd
import numpy as np
import os

from pyomo.environ import (
    Param,
    Var,
    value,
    units as pyunits,
    ConcreteModel,
)

from idaes.core.surrogate.pysmo_surrogate import (
    PysmoRBFTrainer,
    PysmoPolyTrainer,
    PysmoSurrogate,
)
from idaes.core.surrogate.sampling.data_utils import (
    split_training_validation,
)  # Yes, it's a random split
from idaes.core.surrogate.plotting.sm_plotter import (
    surrogate_scatter2D,
    surrogate_parity,
    surrogate_residual,
)
from idaes.core.util.scaling import calculate_variable_from_constraint

from idaes.core.surrogate.pysmo.sampling import LatinHypercubeSampling
from idaes.core.surrogate.surrogate_block import SurrogateBlock
from matplotlib import pyplot as plt
from watertap.core.solvers import get_solver


# Load Data
# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
# Get the directory containing the current script
current_directory = os.path.dirname(current_script_path)
filename = "ro_sweep_USED_IN_PT.csv"
data_path = os.path.join(current_directory, filename)
Data = pd.read_csv(data_path)
# Create PySMO Surrogate Model

# Find the SEC
Data["Feed Flow m3/hr"] = Data["Feed Flow"] * 3600
Data["Total_Permeate_Flow_m3_s"] = Data["Recovery"] * Data["Feed Flow"]
Data["Specific Energy (kWh/m3)"] = (
    Data["Total Power (W)"] / Data["Total_Permeate_Flow_m3_s"] / 3600 / 1000
)
# Pull input and output data
input_data = Data.iloc[:, [0, -3]]  ## RR,feed flow
output_data = Data.iloc[:, -1]  # Specific Energy
input_labels = [Data.columns[0], Data.columns[-3]]
output_labels = [Data.columns[-1]]

# Remove the rows with nan values
Data = Data.dropna(subset=output_labels)

# Check data is all expected
assert pd.to_numeric(Data[input_labels[0]], errors="coerce").notnull().all()
assert pd.to_numeric(Data[output_labels[0]], errors="coerce").notnull().all()

# No need to scale data

# Change this as appropriate
RRmin = min(Data[input_labels[0]])
RRmax = max(Data[input_labels[0]])
flowmin = min(Data[input_labels[1]])
flowmax = max(Data[input_labels[1]])

input_bounds = {"Recovery": (RRmin, RRmax), "Feed Flow m3/hr": (flowmin, flowmax)}

# Sample Data
n_data = output_data.size
# training_fraction = 0.8 # If I have like 30 points, not sure have to do training split
# data_training, data_validation = split_training_validation(Data_Scaled, training_fraction, seed= n_data)
# Create Surrogate
trainer = PysmoPolyTrainer(
    input_labels=input_labels, output_labels=output_labels, training_dataframe=Data
)
trainer.config.maximum_polynomial_order = 1

trained_surr = trainer.train_surrogate()
Surrogate = PysmoSurrogate(trained_surr, input_labels, output_labels, input_bounds)
# Visualize Surrogate
m = ConcreteModel()
m.flowrate = Var()
m.recovery = Var()
m.power = Var()

m.surrogate_blk = SurrogateBlock(concrete=True)
m.surrogate = Surrogate
m.surrogate_blk.build_model(
    m.surrogate,
    input_vars=[m.recovery, m.flowrate],
    output_vars=[m.power],
)
m.surrogate_blk.pysmo_constraint.display()  # display()
# m.surrogate_blk.pysmo_constraint["F_t"].pprint()

minx1, maxx1 = m.recovery.bounds
minx2, maxx2 = m.flowrate.bounds
miny, maxy = m.power.bounds

num_points = 25
x1_vals = np.linspace(minx1, maxx1, num=num_points)
x2_vals = np.linspace(minx2, maxx2, num=num_points)
y_vals = np.zeros((num_points, num_points))
solver = get_solver()
for i in range(num_points):
    for j in range(num_points):
        m.recovery.fix(x1_vals[i])
        m.flowrate.fix(x2_vals[j])
        calculate_variable_from_constraint(
            m.power, m.surrogate_blk.pysmo_constraint["Specific Energy (kWh/m3)"]
        )
        # m.surrogate_blk.display()
        # results = solver.solve(m, tee=True)
        # m.surrogate_blk.display()
        # print(m.flowrate.value, m.power.value)
        y_vals[i, j] = m.power.value
    # assert False

X1, X2 = np.meshgrid(x1_vals, x2_vals, indexing="ij")
x_curve = np.linspace(minx1, maxx1, num=100)
y_curve = 45/(1-x_curve)

fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111)
contour = ax.contourf(X1, X2, y_vals, levels=20, cmap="viridis", alpha=0.85)
# Overlay actual data points
scatter = ax.scatter(
    Data[input_labels[0]],
    Data[input_labels[1]],
    c="black",
    s=80,
    alpha=0.9,
    marker="o",
    edgecolors="black",
    linewidth=1.5,
    label="Param. Sweep Points",
)

# Plot constraint curve
ax.plot(x_curve, y_curve, 'r-', linewidth=2.5, label='Minimum Recovery Constraint')

ax.set_xlabel("RR", fontsize=14)
ax.set_ylabel("Feed Flowrate (m$^3$/hr)", fontsize=14)
ax.set_ylim(flowmin, flowmax)
ax.set_title("Train Power Consumption Surrogate", fontsize=14)
cbar = fig.colorbar(contour, ax=ax, label="Specific Energy (kWh/m$^3$)")
cbar.ax.tick_params(labelsize=14)
ax.tick_params(labelsize=14)
ax.legend(fontsize=14)

# Optionally Show the validation data
# small_val_data = data_validation.sample(n=num_points*2)
# plt.scatter(
#     small_val_data["UV1_mgd"],
#     small_val_data["UV1_kW"],
#     c="k",
#     label='Random Selection of Data Points'
# )
plt.show()

# Residual plot at actual data points: percent difference = 100 * (surrogate - actual) / actual
actual_x1 = Data[input_labels[0]].to_numpy()
actual_x2 = Data[input_labels[1]].to_numpy()
actual_z = Data[output_labels[0]].to_numpy()
predicted_z = np.zeros_like(actual_z, dtype=float)

for k, (x1, x2) in enumerate(zip(actual_x1, actual_x2)):
    m.recovery.fix(x1)
    m.flowrate.fix(x2)
    calculate_variable_from_constraint(
        m.power, m.surrogate_blk.pysmo_constraint["Specific Energy (kWh/m3)"]
    )
    predicted_z[k] = m.power.value

denominator = np.where(np.abs(actual_z) > 1e-12, actual_z, np.nan)
percent_diff = 100.0 * (predicted_z - actual_z) / denominator
valid_mask = np.isfinite(percent_diff)

fig_res = plt.figure(figsize=(10, 8))
ax_res = fig_res.add_subplot(111)

scatter_res = ax_res.scatter(
    actual_x1[valid_mask],
    actual_x2[valid_mask],
    c=percent_diff[valid_mask],
    s=80,
    alpha=0.9,
    marker="o",
    edgecolors="black",
    linewidth=1.5,
    cmap="coolwarm",
)

ax_res.set_xlabel("RR", fontsize=14)
ax_res.set_ylabel("Feed Flowrate (m$^3$/hr)", fontsize=14)
ax_res.set_title("Surrogate Percent Difference from Data Points", fontsize=14)
cbar_res = fig_res.colorbar(
    scatter_res, ax=ax_res, label="Percent Difference (%)"
)
cbar_res.ax.tick_params(labelsize=14)
ax_res.tick_params(labelsize=14)
ax_res.legend(fontsize=14)
plt.show()

# Save Surrogate
surr_name = f"ro_SEC_poly_fit_order_{trainer.config.maximum_polynomial_order}.json"
Surrogate.save_to_file(os.path.join(current_directory, surr_name), overwrite=True)
