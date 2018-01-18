from import_all import *

class OTFT(object):
    def read_trans(self, filename):
        df = pd.read_csv(filename, skiprows=5)
        return df
    

    def read_output(self, filename):
        df = pd.read_csv(filename, skiprows=4)
        return df


    def output_lin(self, vd, mob, cap, width, length, vg, vt):
        i_d = cap * mob * (width/length) * ((vg - vt) * vd - 0.5 * vd**2)
        return i_d


    def output_sat(self, vd, mob, cap, width, length, vg, vt):
        #note that saturation current is independent from Vg.
        
        vd_length = len(vd)
        i_d = 0.5 * cap * mob * (width/length) * (vg - vt)**2
        return np.ones(vd_length) * i_d


    def cal_output(self, vd, mob, cap, width, length, vg, vt):
        #linear curve and saturate cureve cross at Vd = Vg - Vt
        
        if vt > vg: #no output current in this condition
            return np.zeros(len(vd))
            
        else:
            id_lin = self.output_lin(vd, mob, cap, width, length, vg, vt)
            id_sat = self.output_sat(vd, mob, cap, width, length, vg, vt)

            lin_mask = vd <= vg - vt
            sat_mask = np.invert(lin_mask)

            i_d = np.concatenate((id_lin[lin_mask], id_sat[sat_mask]))
            return i_d


    def est_mob(self, v_g, i_d, width, length, cap, fit_start, fit_end):
        """estimate mobility from a transfer characteristics
        
        Args:
        v_g: np.array or df, gate voltage [V]
        i_d: np.array or df, drain current [V]
        width: float, width of the channel [um]
        length: float, length of the channel [um]
        cap: float, capasitance of the dielectric layer [F cm^(-2)]
        fit_start: float, voltage to start linear fitting [V]
        fit_end: float, voltage to end linear fitting [V]
        
        Rets:
        mob: float, mobility [cm2/Vs]
        v_t: float, threshold voltage [V]
        slope: float, slope at the linear region in i_d^0.5 - V_G plot
        intercept: float, intercept of the linear fit line
        """
    
        id_sq = i_d**0.5
        mask = (v_g > fit_start) & (v_g < fit_end)
        vg_masked = v_g[mask]
        id_sq_masked = id_sq[mask]
        
        slope, intercept = np.polyfit(vg_masked, id_sq_masked, 1)
        v_t = -intercept/slope
        
        mob_sq = (2*length/(cap*width))**0.5 * slope
        mob = mob_sq**2
        
        return mob, v_t, slope, intercept


    def plot_transfer(self, df, width, length, cap, fit_start, fit_end, fig_title='', plot_i_g=True, fig_size=(5,5)):
        """plot transfer characteristics

        Args:
        df: pd.DataFrame, data of transfer characteristics
        v_g: np.array or df, gate voltage [V]
        i_d: np.array or df, drain current [V]
        width: float, width of the channel [um]
        length: float, length of the channel [um]
        cap: float, capasitance of the dielectric layer [F cm^(-2)]
        fit_start: float, voltage to start linear fitting [V]
        fit_end: float, voltage to end linear fitting [V]
        fig_title: string, title of figure
        plot_i_g: boolan, plot Ig or not
        fig_size: list (float, float), figure size
        
        Rets:
        parm_list: list, containing the following parameters

        moblity: float, mobility [cm2/Vs]
        v_t: float, threshold voltage [V]
        slope: float, slope at the linear region in i_d^0.5 - V_G plot
        intercept: float, intercept of the linear fit line
        
        """
        f, ax = plt.subplots(figsize=fig_size)
        ax2 = ax.twinx()
        ax.set_yscale('log')
        ax.set_xlabel(r'V_G (V)')
        ax.set_ylabel(r'I_D (A)')
        ax2.set_ylabel('I_D^(1/2) (A^1/2)')
        col_name = df.columns
        parm_list = []
        for col in [col for col in col_name if 'Id' in col]:
            col_label = col.split(' ')[-1].replace(')', '')
            ax.plot(df['Vg'], df[col], label=col_label)
            id_sq = df[col]**(0.5)
            ax2.plot(df['Vg'], id_sq)
            
            mobility, v_t, slope, intercept = self.est_mob(df['Vg'], df[col], width, length, cap,
                                           fit_start, fit_end)
            
            parms = (col_label, mobility, v_t, slope, intercept)
            parm_list.append(parms)
            lin_fit = df['Vg'] * slope + intercept
            ax2.plot(df['Vg'], lin_fit, '--', color='black')
            
            
            print 'V_SD = %s, mobility = %0.2e [cm2/Vs], Vt = %0.1f [V]' %(col_label, mobility, v_t)
            
        ax.legend(loc='best')
        ax2.set_ylim(ymin=0)
        ax.set_title(fig_title)
        plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        
        if plot_i_g:
            ymin, ymax = ax.set_ylim()
            f, ax = plt.subplots(figsize=fig_size)
            ax.set_yscale('log')
            ax.set_xlabel('V_G (V)')
            ax.set_ylabel('I_G (A)')
            ax.set_ylim(ymin, ymax)
            ax.set_title(fig_title)
            for col in [col for col in col_name if 'Ig' in col]:
                ax.plot(df['Vg'], df[col])

     
        return parm_list


    def plot_output(self, df, plot_cal=False, 
                    mob=0, cap=0, width=0, length=0, vt=0, fig_size=(5,5)):
        """plot output characteristics

        Args: pd.DataFrame, data frame of output curve data
        plot_cal: bool, if ture, theoretical curves are plotted based on following parameters
        mob: float, mobility [cm2/Vs]
        cap: float, capacitance [F/cm2]
        width: float, channel width [um]
        length: float, channel length [um]
        vt: float, threshold voltage [V]
        fig_size: list, figure size, default=(5,5)
        """

        f, ax = plt.subplots(figsize=fig_size)

        col_name = df.columns
        for col in [col for col in col_name if 'Id' in col]:
            col_label = col.split(' ')[-1].replace(')', '')
            ax.plot(df['Vd'], df[col], label=col_label, marker='o', markersize=2)
            
            if plot_cal:
                vg = float(col_label[:-1])
                vd_dual = np.array(df['Vd']) #assumed dual sweep
                vd = vd_dual[:len(vd_dual)/2]
                i_d = self.cal_output(vd, mob, cap, width, length, vg, vt)
                ax.plot(vd, i_d, color='black', linestyle='-')
            
        ax.set_xlabel('V_D (V)')
        ax.set_ylabel('I_D (A)')
        ax.legend(loc='best')
        plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
