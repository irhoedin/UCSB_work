from import_all import*

#Basic physical constants
H = 6.63e-34 #[J s] Plank constant
H_eV = 4.135e-15 #[eV s] Plank constant
C = 2.998E8 #[m/s] the speed of light
KB = 1.38e-23 #[J/K] Boltzmann constant
KB_eV = 8.617E-5 #[eV/K] Boltzmann constant
Q = 1.69e-19 #[C] elementary charge

class Voc_rad(object):
    """Calculating radiative Voc.
    
    Reffered SI of DOI: 10.1038/nenergy.2016.89.
    """
    
    def cal_blackbody_spec(self, wl, temp, graph=False):
        """calculate blackbody radiation spectrum based on the Plank's law
        
        These websites are useful.
        http://www.oceanopticsbook.info/view/light_and_radiometry/level_2/blackbody_radiation
        http://www.spectralcalc.com/blackbody/blackbody.html
        
        Args:
        wl: np.array, wavelength in [nm]
        temp: float, temperature in [K]
        graph: boolan, if true, plot blackbody photon flux spectrum against enegy in [eV]
        
        Ret:
        bb_spce: np.array [s-1 m-2 eV-1]
        """
        
        #calculate number of photons per second in one square meters in every eV
        
        wl_m = wl* 1e-9 # [nm] -> [m]
    
        bb_spec = (2. * 3.1415 * C) / wl_m**4 \
                    * (1 / (np.exp((H * C)/(wl_m * KB * temp)) - 1)) * 1e-9
                 
        if graph:
            f, ax = plt.subplots(figsize=(6,6))
            ax.plot(wl, bb_spec)
            ax.set_title('Blackbody spectrum at %0.f K' %temp)
            ax.set_xlabel('wavelength [wl]')
            ax.set_ylabel('photon [s-1 m-2 nm-1]')
            ax.set_yscale('log')
        
        return bb_spec
    
    def load_eqe_file(self, filename, graph=False):
        """load eqe file and interpolate in eV scale
        
        Args:
        filename: string, filename of eqe data file.
                  Tab separated, no header, column0: wavelength, column1: eqe spectrum
        grpah: boolan, if true, plot eqe against enegy in [eV]
        
        Ret:
        eqe_wl: np.array, wavelength [nm]
        eqe_spec: np.array, eqe [-]
        """
        
                          
        eqe_df = pd.read_csv(filename, sep='\t', header=None)
        eqe_wl = eqe_df.ix[:,0]
        eqe_spec = eqe_df.ix[:,1]
        
        if graph:
            f, ax = plt.subplots(figsize=(6,6))
            ax.plot(eqe_wl, eqe_spec, 'o')
            ax.set_title('EQE')
            ax.set_yscale('log')
            
        return eqe_wl, eqe_spec
                
        
    def cal_main(self, filename, temp, jsc, voc, show_graph=False):
        """calculate j0, Voc_rad, and d_Voc_nonrad.
        
        Args:
        filename: string, filename of eqe data file. See load_eqe_file().
        temp: float, temperature in K
        jsc: float, jsc of the device in [mA/cm2]
        voc: float, voc of the device in [V]
        graph: boolan, if ture, plot blackbody and eqe spectra against energy in eV
        
        Rets:
        j0: float, dark saturation current density [A/m2]
        voc_rad: float, radiative open circuit voltage [V]
        d_voc_nonrad: float, non-radiative recombination term: Voc_rad - Voc [V]
        """

        from scipy.integrate import trapz

        eqe_wl, eqe_spec = self.load_eqe_file(filename, show_graph)
        bb_spec = self.cal_blackbody_spec(eqe_wl, temp, show_graph)
        
        #Eq (SI4): the Raw's reciprocity relation when the recombination is 100% radiative
        j0 = Q * trapz(bb_spec * eqe_spec, eqe_wl)
        
        jsc_Am2 = jsc * 1e-3 / (1e-2)**2 #[mA/cm2] to [A/m2]
        
        #Eq(SI1)
        voc_rad = (KB * temp) / Q * np.log((jsc_Am2 / j0) + 1)
        
        d_voc_nonrad = voc_rad - voc
        
        print 'j0 = %0.3e [A/m2]\n' %j0 + \
              'Voc_rad = %0.3f [V]\n' %voc_rad + \
              'delta Voc_nonrad = %0.3f [V]' %d_voc_nonrad
        
        return j0, Voc_rad, d_voc_nonrad



class Voc_rad_xls(Voc_rad):
    """read EQE data from excel which prepared by Hengbin"""

    def __init__(self, sheet_name, column_num):
        self.sheet_name = sheet_name
        self.column_num = column_num
        
    def load_eqe_file(self, xlsname, graph=False):

        df = pd.read_excel(xlsname, sheet=self.sheet_name)
        
        wl = df.ix[:,0]
        eqe = df.ix[:,self.column_num]
        data_name = eqe.name
        eqe_dnan = eqe.dropna()
        eqe_len = len(eqe_dnan.index)
        wl_dnan = wl.iloc[:eqe_len]
        
        if graph:
            f, ax = plt.subplots(figsize=(6,6))
            ax.plot(wl_dnan, eqe_dnan, 'o')
            ax.set_title('EQE')
            ax.set_yscale('log')

        print data_name
        return wl_dnan, eqe_dnan
        

