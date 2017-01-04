from import_all import *
from scipy import interpolate

AM15PATH = '/Users/nakayamahidenori/my_python_modules/ASTMG173.xls'

class AM15G(object):
    """Instance containing AM15G spectrum data
    
    self.wl: np.array, wavelength [nm]
    self.spec: np.array, AM15G spectrum
    
    """
    
    def __init__(self, start=300, end=1000, AM15G_excel=AM15PATH):
        """Initiate the instance.
        Read the excel file of AM15G spectrum,
        interpolate the spectrum,
        extract the spectrum data according to the wavelength range (1 nm pitch).
        
        Args:
        start - float: wavelength to start [nm]
        end - float: wavelength to end [nm]
        AM15F_excel - string: dirctory +filename of the excel file.
        """
        self.PLANK_CONST = 6.626e-34  #[J/s]
        self.LIGHT_SPEED = 299792458  #[m/s]
        self.ELEM_CHARGE = 1.602e-19  #[C]
               
        self.wl = np.linspace(start, end, int(end - start + 1))
        
        am15g_df = pd.read_excel(AM15G_excel, sheet = 'SMARTS2', skiporiows = 0, header = 1)
        am15g_wl = am15g_df.ix[:,0]  #[nm]
        am15g_power = am15g_df.ix[:,2]  #[W/m^2/nm]
        am15g_f = interpolate.interp1d(am15g_wl, am15g_power)
        self.spec = am15g_f(self.wl)
     

class QE2Jsc(AM15G):
    """Read a csv file of IPCE quantum yield and calculate Jsc.
    
    self.jsc: float, calculated Jsc [mA/cm^2]
    self.wl: float, wavelength of Jsc calculation reange (1 nm pitch) [nm]
    self.spec: np.array, AM15G spectrum  [W/m^2/nm]
    self.qe: np.array, quantum yeild spectrum
    self.qe_masked: np.arrapy, quantum yeild spectrum in the designated wavelength range
    """
    
    def __init__(self, filename, start=300, end=1000, AM15G_excel=AM15PATH):
        AM15G.__init__(self, start=300, end=1000, AM15G_excel=AM15PATH)
        
        qe_df = pd.read_csv(filename, skiprows = 18, header=None, dtype=np.float32)
        qe_df.columns= ['wavelength nm', 'quantum_yield']
        self.qe_wl = qe_df.ix[:,0]
        self.qe = qe_df.ix[:,1]
        mask = (self.qe_wl >= start) & (self.qe_wl <= end)
        self.qe_masked = np.array(self.qe[mask])
        self.calculate_jsc()
        
    def calculate_jsc(self):
        photon_energy_spec = self.PLANK_CONST * self.LIGHT_SPEED / (self.wl / 1e9)  #[J]
        photon_count_spec = self.spec / photon_energy_spec  #[1/s/m^2/nm]
        current_per_wavelength = self.ELEM_CHARGE * (photon_count_spec * self.qe_masked)  #[A/m^2/nm]
        jsc_estimated = current_per_wavelength.cumsum().max() * 1000 / 100**2  #[A/m^2] to [mA/cm^2]
        self.jsc = jsc_estimated
        
class SimQE2Jsc(QE2Jsc):
    
    def __init__(self, width=(300, 750), qe=1, start=300, end=1000, AM15G_excel=AM15PATH):
        AM15G.__init__(self, start, end, AM15G_excel=AM15PATH)
        
        region_list = [np.arange(start, width[0]),
                       np.arange(width[0], width[1]),
                       np.arange(width[1], end)]
        
        r1qe = np.zeros(len(region_list[0]))
        r2qe = np.ones(len(region_list[1]) + 1) * qe
        r3qe = np.zeros(len(region_list[2]))
        
        self.qe_masked = np.hstack([r1qe, r2qe, r3qe])
        
        self.calculate_jsc()

        
class Sens2Jsc(QE2Jsc):
    """Read a csv file of IPCE sensitivity [A/W] and calculate Jsc.
    Refer QE2Jsc class.
    
    self.qe: np.array, sensitivity spectrum
    self.qe_masked: np.array, sensitivity spectrum in the designated wavelength range
    """
    
    def calculate_jsc(self):
        current_per_wavelength = self.spec * self.qe_masked
        jsc_estimated = current_per_wavelength.cumsum().max() * 1000 / 100**2  #[A/m^2] to [mA/cm^2]
        self.jsc = jsc_estimated        



class SynAbs(object):
    def cal_abs_coeff(self, filepath, thickness, sub_filepath,
                      start, end,
                      output_path='/Users/nakayamahidenori/UCSB_data/spectra/abs_coeff',
                      output=True):
        """calculate absorption coefficient from transmittance files.
        
        Args:
        filepath: string, path and file of the transmittance txt file of film
        thickness: float, thickness of the film [nm]
        sub_filepath: strign, path and file of the transmittance txt file of glass/ITO/ZnO substrate
        start: float, wavelength range start point
        end: float, wavlenght range end point

        rets:
        wl: np.array, wavelength [nm]
        ev: np.array, energy volt [eV]
        abs_coeff_wl: np.array, absorption coefficient in wavlength[nm] scale
        abs_coeff_ev: np.array, absorption coefficient in energy [eV] scale
        """
        
        NM_TO_EV_CONST = 1240. #lambda = 1240/E
        
        filename = filepath.split('/')[-1].split('.')[0]
        
        from scipy import interpolate

        
        def interp(wl, absorbance, start=start, end=end, step=1.): 
            f = interpolate.interp1d(wl, absorbance)
            new_wl = np.arange(start, end + step, step)
            new_abs = f(new_wl)
            
            return new_wl, new_abs
            
        f_abs = Clab_UV().read_file(filepath, absorbance=True)
        sub_abs = Clab_UV().read_file(sub_filepath, absorbance=True)
        
        wl, f_abs_intp = interp(f_abs.ix[:,0], f_abs.ix[:,1])
        wl, sub_abs_intp = interp(sub_abs.ix[:,0], sub_abs.ix[:,1])
        abs_coeff_wl = (f_abs_intp - sub_abs_intp)/(thickness*1e-7)
        
        ev_converted = NM_TO_EV_CONST/wl
        ev_start = round(NM_TO_EV_CONST/end + 0.01, 2)
        ev_end = round(NM_TO_EV_CONST/start - 0.01, 2)
        

        ev, abs_coeff_ev = interp(ev_converted, abs_coeff_wl,
                                  start=ev_start, end=ev_end, step=.01)

        
        if output:
            df = pd.DataFrame([np.array(wl),
                               np.array(abs_coeff_wl),
                              np.array(ev),
                              np.array(abs_coeff_ev)],
                              index=['wl_[nm]',
                                     'abs_coeff_wl_[cm-1]',
                                     'energy_[eV]',
                                     'abs_coeff_ev_[cm-1]']).T
            
            df.to_csv(output_path + '/' + filename + '.csv')

        return wl, abs_coeff_wl, ev, abs_coeff_ev
    
    def synthesize_specs(self, wl, p_abs_coeff, n_abs_coeff, p_ratio, thickness):
        """synthesize p/n absorption with designated p-type ratio and thickness
        
        Args:
        wl: np.array, wavelength [nm]
        p_abs_coeff: np.array, absorption coefficient of p-type material
        n_abs_coeff: np.array, absorption coefficient of n-type material
        p_ratio: float, p-type ratio 0-1.
        thickness: float, thickness of film in [nm]
        
        Ret:
        syn_abs: np.array, synthesized absorption spectrum
        """
        
        syn_abs = ((p_ratio * p_abs_coeff) + ((1-p_ratio) * n_abs_coeff)) * (thickness * 1e-7)
        
        return wl, syn_abs



class Abs2Jsc(QE2Jsc, SynAbs):
    """read absorbance and convert to estimated Jsc under the assumption of arbiturary IQE)"""
    from scipy import interpolate

    def __init__ (self):
        return None

    def cal_jsc(self, wl, absorbance, IQE=.8, start=300., end=1000., AM15G_excel=AM15PATH):
        """ initialize the class
        
        Args:
        abs_df: dataframe. column0: wavelength (1 nm pitch), column1: absorbance.
        IQE: float, IQE value.
        start: float, start point of wavelength caliculation.
        end: float, end point of wavelength caliculation.
        """


        AM15G.__init__(self, start=start, end=end, AM15G_excel=AM15PATH)
        f = interpolate.interp1d(wl, absorbance)
        new_wl = range(int(start), int(end) + 1)
        new_abs = f(new_wl)
        transmittance = 10**(-new_abs)
        absorption_rate = 1 - transmittance
        self.qe_masked = IQE * np.array(absorption_rate)
        self.calculate_jsc()
        return self.jsc


    def cal_syn_jsc(self, wl, p_abscoeff, n_abscoeff, p_ratio, thickness,
                    IQE=.8, start=300., end=1000., AM15G_excel=AM15PATH):
        wl, syn_abs = self.synthesize_specs(wl, p_abscoeff, n_abscoeff, p_ratio, thickness)
        jsc = self.cal_jsc(wl, syn_abs, start=start, end=end, IQE=IQE)
        return jsc



    def build_map(self, figname, p_filepath, n_filepath,
                  IQE=.8, start=300., end=1000., AM15G_excel=AM15PATH,
                  ratio_step=21, t_start=100, t_end=400, t_step=51,
                  figsavepath='/Users/nakayamahidenori/UCSB_data/spectra/jsc_map/',
                  spec_t=250, savespec=True):
        
        
        p_df = pd.read_csv(p_filepath, index_col=0)
        p_wl = p_df.ix[:,0]
        p_abscoeff = p_df.ix[:,1]

        n_df = pd.read_csv(n_filepath, index_col=0)
        n_abscoeff = n_df.ix[:,1]

        ratio_list = np.linspace(0,1, ratio_step)
        thickness_list = np.linspace(t_start, t_end, t_step)
        ratio, thickness = np.meshgrid(ratio_list, thickness_list)


        data = np.array([self.cal_syn_jsc(p_wl, p_abscoeff, n_abscoeff, r, t, start=start, end=end)
                         for t in thickness_list for r in ratio_list])
        data.resize(t_step, ratio_step)


        f, ax = plt.subplots()
        im = ax.pcolor(ratio, thickness, data, cmap='RdBu_r')
        f.colorbar(im)
        ax.set_xlabel('p ratio')
        ax.set_ylabel('thickness [nm]')
        
        title = figname + ', IQE=' + str(IQE)
        ax.set_title(title)

        f.savefig(figsavepath + figname + '.pdf')


        f2, ax2 = plt.subplots()

        if savespec:
            sns.set_palette("ocean")

            for pr in np.linspace(0,1,5):
                wl, syn_abs = self.synthesize_specs(p_wl, p_abscoeff, n_abscoeff, pr, spec_t)

                ax2.plot(wl, syn_abs)
            
            ax2.set_xlabel('wavelength [nm]')
            ax2.set_ylabel('Absorbance')
            ax2.set_title(figname + ' t = ' + str(spec_t) + ' nm')

            f2.savefig(figsavepath + figname + '_2D.pdf')
