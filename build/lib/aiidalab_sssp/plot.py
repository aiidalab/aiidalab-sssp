import numpy as np
import matplotlib.pyplot as plt

def delta_measure_hist(pseudos: dict, measure_type):

    px = 1/plt.rcParams['figure.dpi']  # pixel in inches
    fig, ax = plt.subplots(1, 1, figsize=(1024*px, 360*px))
    cmap = plt.get_cmap('tab20')
    NUM_COLOR = 20
    structures = ['X', 'XO', 'X2O', 'XO3', 'X2O', 'X2O3', 'X2O5']
    num_structures = len(structures)

    # element
    try:
        v0 = list(pseudos.values())[0]
        element = v0['pseudo_info']['element']
    except:
        element = None

    if measure_type == 'delta':
        keyname = 'delta'
        ylabel = 'Δ -factor'
    elif measure_type == 'nv_delta':
        keyname = 'rel_errors_vec_length'
        ylabel = 'νΔ -factor'

    for i, (label, output) in enumerate(pseudos.items()):
        N = len(structures)
        idx = np.arange(N) # the x locations for the groups
        width = 0.1       # the width of the bars

        y_delta = []
        for structure in structures:
            try:
                res = output['delta_factor']['output_delta_analyze'][f'output_{structure}']
                y_delta.append(res[keyname])
            except:
                y_delta.append(-1)

        _, pp_family, pp_z, pp_type, pp_version = label.split('/')
        out_label = f'{pp_z}/{pp_type}({pp_family}-{pp_version})'

        ax.bar(idx+width*i, y_delta, width, color=cmap(i/NUM_COLOR), label=out_label)
        ax.legend()
        ax.set_title(f'X={element}')
        
    ax.axhline(y=1.0, linestyle='--', color='gray')
    ax.set_ylabel(ylabel)
    ax.set_ylim([0, 10])
    ax.set_yticks(np.arange(10))
    ax.set_xticks(list(range(num_structures)))
    ax.set_xticklabels(structures)

    return fig

def convergence(pseudos: dict, wf_name, measure_name, ylabel, threshold=None):
    
    px = 1/plt.rcParams['figure.dpi']
    fig, (ax1, ax2) = plt.subplots(1, 2, gridspec_kw={'width_ratios': [2, 1]}, figsize=(1024*px, 360*px))
    cmap = plt.get_cmap('tab20')
    NUM_COLOR = 20
    

    for i, (label, output) in enumerate(pseudos.items()):
        # Calculate the avg delta measure value
        structures = ['X', 'XO', 'X2O', 'XO3', 'X2O', 'X2O3', 'X2O5']
        lst = []
        for structure in structures:
            try:
                res = output['delta_factor']['output_delta_analyze'][f'output_{structure}']
                lst.append(res['rel_errors_vec_length'])
            except:
                pass

        avg_delta = sum(lst) / len(lst)


        try:
            res = output[wf_name]
            x_wfc = res['output_parameters_wfc_test']['ecutwfc']
            y_wfc = res['output_parameters_wfc_test'][measure_name]

            x_rho = res['output_parameters_rho_test']['ecutrho']
            y_rho = res['output_parameters_rho_test'][measure_name]

            wfc_cutoff = res['final_output_parameters']['wfc_cutoff']

            _, pp_family, pp_z, pp_type, pp_version = label.split('/')
            out_label = f'{pp_z}/{pp_type}(νΔ={avg_delta:.2f})({pp_family}-{pp_version})'

            ax1.plot(x_wfc, y_wfc, marker='o', color=cmap(i/NUM_COLOR), label=out_label)
            ax2.plot(x_rho, y_rho, marker='o', color=cmap(i/NUM_COLOR), label=f'cutoff wfc = {wfc_cutoff} Ry')
        except:
            pass

    ax1.set_ylabel(ylabel)
    ax1.set_xlabel('Wavefuntion cutoff (Ry)')
    ax1.set_title('Fixed rho cutoff at 200 * dual (dual=4 for NC and dual=8 for non-NC)')

    # ax2.legend(loc='upper left', bbox_to_anchor=(1, 1.0))
    ax1.legend()

    ax2.set_xlabel('Charge density cudoff (Ry)')
    ax2.set_title('Convergence test at fixed wavefunction cutoff')
    ax2.legend()

    if threshold:
        ax1.axhline(y=threshold, color='r', linestyle='--')
        ax2.axhline(y=threshold, color='r', linestyle='--')

        ax1.set_ylim(-0.5 * threshold, 10*threshold)
        ax2.set_ylim(-0.5 * threshold, 10*threshold)

    plt.tight_layout()

    return fig