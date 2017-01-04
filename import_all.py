import numpy as np
import pandas as pd
from scipy.optimize import curve_fit 
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style("whitegrid")
sns.set_context("poster")
sns.set_palette("husl")

class U4100(object):
    """Handles text data from U4100 in 1213.

    functions:
    read_file(adr, absorbance=True),
    read_all_file(adr, absorbance=True),
    show_plot_all(adr, absorbance=True, xlim=[300,800], ylim=[-0.05, 2])
    """
    
    def __init__(self):
        self.ext = '.TXT'
        self.skipfooter = 1
        self.sep = '\t'
        self.start_key = 'nm\t'
        
    def find_skiprows(self, adr):
        for i, line in enumerate(open(adr)):
            if self.start_key in line:
                self.skiprows = i + 1
                break
        
    
    def read_file(self, adr, absorbance=True):
        """read tsv data 

        Arguments:
        adr: string, address + filename of the file
        absorbance: boolan, if the file contains transimttance,
        then input False.

        Ret: dataframe.
        column0: "wavelength"
        column1: "filename_Abs" or "filename_Trsns"
        """
        
        self.find_skiprows(adr)
        print self.skiprows

        filename = adr.split('/')[-1].split('.')[0]
        data = pd.read_csv(adr,
                           skiprows=self.skiprows,
                           skipfooter=self.skipfooter,
                           sep=self.sep,
                           header=None)
        
        if absorbance:
            data.columns = ['wavelength', filename + '_Abs']

        else:
            data.columns = ['wavelength', filename + '_Trans']

        return data
    
    def read_all_files(self, adr, absorbance=True):
        """read all UV files in adr and return one DataFrame"""

        import pandas as pd
        import glob
        
        file_list = glob.glob(adr + '/*' + self.ext + '*')

        master_data = pd.DataFrame([])
        for i, _file in enumerate(file_list):
            data = self.read_file(_file, absorbance=absorbance)
            
            if i ==0:
                master_data = data
                
            if i > 0:
                master_data = pd.concat([master_data, data.ix[:,1]], axis=1)
                
        return master_data

    def read_label(self, adr, filename):
        """read a tsv file to match data filename and legend.

        tsv file should contain data filename in column 0, and lagend in column 1.
        """
        adr_filename = adr + '/' + filename
        label_df = pd.read_csv(adr_filename, header=None, index_col=0, sep='\t')
        label_df.columns = ["label"]

        return label_df
    
    def show_plot_all(self, adr, label_file="", absorbance=True, xlim=[300,800], ylim=[-0.05, 2]):
        master_data = self.read_all_files(adr, absorbance=absorbance)
        if label_file:
            label_df = self.read_label(adr, label_file)

        f, ax = plt.subplots()
    
        for i in range(1, len(master_data.columns)):
            column_name = master_data.columns[i]
            if label_file:
                label_name = label_df.ix[column_name.split('_')[0], "label"]

            else:
                label_name = column_name

            ax.plot(master_data.ix[:,0], master_data.ix[:,i],
                    label = label_name)
        
        ax.legend(loc='best')
        ax.set_xlim(xlim[0], xlim[1])
        ax.set_ylim(ylim[0], ylim[1])
        ax.set_xlabel('wavelength [nm]')
        if absorbance:
            ax.set_ylabel('Absorbance')
        else:
            ax.set_ylabel('Transmittance')
        return master_data

    
class GB3_UV(U4100):
    def __init__(self):
        
        self.ext = '.Master'
        self.skipfooter = 1
        self.sep = '\t'
        self.start_key = '>>>>>Begin'

class Clab_UV(GB3_UV):
    """Handles text data from inline UV spectrum equipment in GB3.
    This equipment records only transmittant.
    If, absorbance=True, then transmittat data is converted to absorbance.

    functions:
    read_file(adr, absorbance=True),
    read_all_files(adr, absorbance=True),
    show_plot_all(adr, absorbance=True, xlim=[300,800], ylim=[-0.05, 2])
    """
    def __init__(self):
        GB3_UV.__init__(self)
        self.ext ='.txt'
        
    def read_file(self, adr, absorbance=True):
        data = U4100.read_file(self, adr, absorbance=absorbance)

        if absorbance:
            data.ix[:,1] = -np.log10(data.ix[:,1]/100)

        return data


class DCR_UV(U4100):
    """Handles text data from UV measurement setup in C41-116.
    The setup records only transmittance, no absorbance.

    functions:
    read_file(adr, absorbance=True),
    read_file(adr, absorbance=True),
    read_all_file(adr, absorbance=True),
    show_plot_all(adr, absorbance=True, xlim=[300,800], ylim=[-0.05, 2])
    """

    def __init__(self):
        self.ext = '.txt'
        self.skipfooter = 0
        self.sep = '\t'
    
    def find_skiprows(self,adr):
        self.skiprows=0

    def read_file(self, adr, absorbance=True):
        data = U4100.read_file(self, adr, absorbance=absorbance)

        if absorbance:
            data.ix[:,1] = -np.log10(data.ix[:,1])

        return data

