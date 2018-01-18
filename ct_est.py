from import_all import *
def est_ct_from_eqe(x_data, y_data, title = "",
                    fit_start=1.0, fit_end=1.5, lm_guess=0.2, ct_guess=1.5, fit_curve_end=2.,
                    figx=5, figy=5, xlim_low=1., xlim_high=2.):
    """ fit the subband of EQE with a Marcus theory curve on CT state absorption.
    See DOI: 10.1002/adma.201600281.
    Return a list of scaling factor, E_CT, and reorientation energy (lambda).
    show up energy-EQE graph with fitted curve

    Args:
    x_data: pd.Series. a list of wavelength [nm] 
    y_data: pd.Series. a list of EQE
    Note that the length of x_data and y_data is same and they do not include inf or nan.
    fit_start: start point of curve fitting [eV]
    fit_end: end point of curve fitting [eV]
    lm_guess: initial guess of lambda [eV]
    ct_guess: initial guess of E_CT [eV]
    fit_curve_end: end point of fitted curve drowing [eV]
    figx: float, figure size along x
    figy: float, figure size along y
    xlim_low: float, x lim lower limit
    xlim_high: float, x lim higher limit
    
    Rets:
    sf_fitted : scaling factor
    lambda_fitted: lambda (reorientation energy) [eV]
    e_ct_fitted: E_CT [eV]
    """
    
    import scipy.optimize
    sns.set_style("ticks")
    
    K_BOLTZ = 8.617e-5 #[eV/K]
    TEMP = 300 #[K]
    SF_INIT = 0.01 #initial guess for the scaling factor of the fitting curve

    def ct_curve(engy, sf, lm, e_ct):
        ct_eq = sf * (1/(engy * (4 * np.pi * lm * K_BOLTZ * TEMP)**0.5) *\
                      np.exp((-(e_ct + lm - engy)**2)/(4 * lm * K_BOLTZ * TEMP)))
        return ct_eq
    
    x_data_ev = 1240/x_data #[nm] to [eV]
    mask = (x_data_ev > fit_start) & (x_data_ev < fit_end)
    x_masked = x_data_ev[mask]
    y_masked = y_data[mask]    
    
    f, ax = plt.subplots(figsize=(figx, figy))
    ax.plot(x_data_ev, y_data, 'o-', color='black')
    ax.set_yscale('log')
    ax.set_ylim(1e-7, 1.1)
    ax.set_xlim(xlim_low, xlim_high)
    ax.set_xlabel('Evergy [eV]')
    ax.set_ylabel('IPCE [-]')
    ax.set_title(title)
    
    try:
        init_guess = np.array([SF_INIT, lm_guess, ct_guess])
        opt, conv = scipy.optimize.curve_fit(ct_curve, x_masked, y_masked, p0=init_guess)

        sf_fitted = opt[0]
        lambda_fitted = opt[1]
        e_ct_fitted = opt[2]
        print ' lambda = %0.2f eV\n E_CT = %0.2f eV\n scaling factor = %0.3e'\
        %(lambda_fitted, e_ct_fitted, sf_fitted)

        fit_x = np.linspace(x_data_ev.iloc[-1], fit_curve_end, 50) 
        fit_curve = ct_curve(fit_x, opt[0], opt[1], opt[2])    

        ax.plot(fit_x, fit_curve, ls='dashed', color='black')


        return sf_fitted, lambda_fitted, e_ct_fitted
    
    except RuntimeError:
        
        print RuntimeError
        return np.nan, np.nan, np.nan

    
def get_eqe(filename):
    eqe = pd.read_csv(filename,sep='\t',header=None,usecols=[0,1])
    x_data = eqe.loc[:,0]
    y_data = eqe.loc[:,1]
    
    return x_data, y_data


def get_eqe_series(df, n):
    """ get wl, eqe serieses and data name from dataframe.
    Drop nan value and make the point number of wl and eqe same.
    
    the first column of the dataframe is "wavelength"
    """
    wl = df.ix[:,0]
    eqe = df.ix[:,n]
    data_name = eqe.name
    eqe_dnan = eqe.dropna()
    eqe_len = len(eqe_dnan.index)
    wl_dnan = wl.iloc[:eqe_len]
    
    return wl_dnan, eqe_dnan, data_name
