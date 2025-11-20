import pandas as pd
import numpy as np
import os

from pyomo.environ import (
    Param,
    Var,
    Suffix,
    NonNegativeReals,
    value,
    units as pyunits,
)

from idaes.core.surrogate.pysmo_surrogate import (
    PysmoRBFTrainer,
    PysmoPolyTrainer,
    PysmoSurrogate,
)
from idaes.core.surrogate.sampling.data_utils import split_training_validation # Yes, it's a random split
from idaes.core.surrogate.plotting.sm_plotter import surrogate_scatter2D, surrogate_parity, surrogate_residual
from idaes.core.surrogate.pysmo.sampling import LatinHypercubeSampling
from matplotlib import pyplot as plt
# Load data
Data = pd.read_csv("c:\\Users\\rchurchi\\flex_desal\\src\\wrd\\data\\WRD_UV_Surrogate_Data.csv")
Data = Data.iloc[1:100,:] # Shorten the amount of data to get working
input_data = Data.iloc[:,1] # UV 1 flow rate
output_data = Data.iloc[:,3] # UV 1 power
input_labels = [Data.columns[1]]
output_labels = [Data.columns[3]]

#plt.plot(input_data.iloc[0:1000],output_data.iloc[0:1000],'.')
#plt.show()

# Check data is all expected
assert pd.to_numeric(Data[input_labels[0]],errors='coerce').notnull().all()
assert pd.to_numeric(Data[output_labels[0]],errors='coerce').notnull().all()

#Data Filters
assert all(Data[input_labels[0]] >= 0)
assert all(Data[output_labels[0]] >= 0)
Data = Data[Data[input_labels[0]] >= 1] # UV 1 flow rate min 1 mgd


# Scale Data
Data_scaled = Data
Data_scaled[output_labels[0]] = Data[output_labels[0]].mul(1e-2)
xmin = min(Data_scaled[input_labels[0]])
xmax = max(Data_scaled[input_labels[0]])

# input_bounds = {input_labels[i]: (xmin[i], xmax[i]) for i in range(len(input_labels))}
input_bounds = {'UV1_mgd': (xmin,xmax)}

# Sample Data
n_data = output_data.size
training_fraction = .8
data_training, data_validation = split_training_validation(Data_scaled,training_fraction,seed=n_data)
#b = LatinHypercubeSampling(Data_scaled,100,sampling_type="selection",xlabels = input_labels, ylabels = output_labels) # A single output variable (y) is assumed to be supplied in the last column if xlabels and ylabels are not supplied.
#data_training = b.sample_points()
# Create the trainer
fittype = "rbf"
if fittype == "rbf":
    trainer = PysmoRBFTrainer(input_labels=input_labels,output_labels=output_labels,training_dataframe=data_training, basis_function='linear')
elif fittype == "poly":
    trainer = PysmoPolyTrainer(input_labels=input_labels,output_labels=output_labels,training_dataframe=data_training)
    trainer.config.maximum_polynomial_order = 4

# Train Data
trained_surr = trainer.train_surrogate()
# Display
Surrogate = PysmoSurrogate(
    trained_surr,
    input_labels,
    output_labels,
    input_bounds,
)

if fittype == "rbf":
    x_tests = pd.DataFrame({"UV1_mgd": [3.0,3.5,4.0]})
    y_unsampled = Surrogate.evaluate_surrogate(x_tests) # IDAES Issue. Evaluate_surrogate fails for polynomial fits

    # Visualize Model Fit
    #b = LatinHypercubeSampling(Data_scaled,100,sampling_type="selection",xlabels = input_labels, ylabels = output_labels) # A single output variable (y) is assumed to be supplied in the last column if xlabels and ylabels are not supplied.
    data_space = np.linspace(xmin,xmax,100)
    small_data_validation = pd.DataFrame({input_labels[0]: data_space})

    #surrogate_parity(Surrogate,small_data_validation,filename='parity_linear1.pdf',show=True)
    #surrogate_parity(Surrogate,data_validation.iloc[300:700],filename='parity_linear2.pdf',show=True)
    #surrogate_scatter2D(Surrogate, small_data_validation, filename='scatter2D_1.pdf', show=True)
    plt.scatter(small_data_validation['UV1_mgd'],Surrogate.evaluate_surrogate(small_data_validation),c='r')
    plt.xlabel("UV1_mgd")
    plt.ylabel("UV1_kW [Predicted]")
    plt.title("UV Energy Surrogate linspace")
    #surrogate_scatter2D(Surrogate, data_validation.iloc[300:700], filename='scatter2D_2.pdf', show=True)
    # Save surrogate
    Surrogate.save_to_file('UV_surr_rbf_linear_full.json',overwrite = True)
elif fittype == "poly":
    print(None)
